from __future__ import annotations

"""Clinical Reader Agent â€” extracts structured evidence from patient records using NLP + LLM."""

import time
import uuid
import structlog

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_evidence import ClinicalEvidence
from app.models.prior_auth import PriorAuthRequest, PAStatus
from app.services import gemini
from app.services.fhir import fhir_client
from app.services.audit import log_action
from app.config import get_settings

logger = structlog.get_logger()


def _run_nlp_preprocessing(text: str) -> dict:
    """Run NLP preprocessing with graceful fallback."""
    try:
        from app.services.nlp import preprocess_clinical_text
        return preprocess_clinical_text(text)
    except Exception as exc:
        logger.warning("clinical_reader.nlp_fallback", error=str(exc))
        return {}


def _fetch_rag_context(cpt_code: str, icd_codes: list[str]) -> str:
    """Fetch RAG context with graceful fallback."""
    try:
        from app.services.rag import retrieve_context_for_evidence
        return retrieve_context_for_evidence(cpt_code, icd_codes)
    except Exception as exc:
        logger.warning("clinical_reader.rag_fallback", error=str(exc))
        return ""


class ClinicalReaderAgent:
    """Scans unstructured patient notes to extract medical necessity evidence.
    Enhanced with NLP preprocessing and RAG context retrieval."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def process(self, pa_request: PriorAuthRequest, clinical_notes: str | None = None) -> ClinicalEvidence:
        logger.info("clinical_reader.start", pa_id=str(pa_request.id), cpt=pa_request.cpt_code)
        start = time.monotonic()

        pa_request.status = PAStatus.CLINICAL_REVIEW
        self.db.flush()

        # 1. Gather clinical text
        notes_text = clinical_notes or ""
        if pa_request.patient.fhir_patient_id and not clinical_notes:
            try:
                notes_text = fhir_client.build_patient_clinical_text(
                    pa_request.patient.fhir_patient_id
                )
            except Exception as exc:
                logger.warning("clinical_reader.fhir_fetch_failed", error=str(exc))

        if not notes_text.strip():
            logger.warning("clinical_reader.no_notes", pa_id=str(pa_request.id))
            notes_text = "No clinical notes available."

        # 2. NLP preprocessing â€” abbreviation expansion, NER, negation detection
        nlp_results = _run_nlp_preprocessing(notes_text)
        enhanced_text = nlp_results.get("expanded_text", notes_text)

        # Build NLP context for LLM
        nlp_context = ""
        if nlp_results:
            entities = nlp_results.get("entities", [])
            medications = nlp_results.get("medications", [])
            conditions = nlp_results.get("conditions", [])
            icd_codes = nlp_results.get("icd_codes", [])
            lab_results = nlp_results.get("lab_results", [])
            negated = nlp_results.get("negated_entities", [])

            def _to_str_list(items):
                return [x if isinstance(x, str) else str(x) for x in items]

            parts = []
            if medications:
                parts.append(f"Medications found: {', '.join(_to_str_list(medications))}")
            if conditions:
                parts.append(f"Conditions: {', '.join(_to_str_list(conditions))}")
            if icd_codes:
                str_codes = _to_str_list(icd_codes)
                parts.append(f"ICD-10 codes: {', '.join(str_codes)}")
                # Auto-populate ICD-10 codes on the PA request if not provided
                if not pa_request.icd10_codes:
                    pa_request.icd10_codes = str_codes
            if lab_results:
                parts.append(f"Lab values: {', '.join(_to_str_list(lab_results))}")
            if negated:
                parts.append(f"Negated findings: {', '.join(_to_str_list(negated))}")
            if parts:
                nlp_context = "\n[NLP Pre-analysis]\n" + "\n".join(parts) + "\n"

        # 3. RAG context â€” retrieve relevant policy/literature context
        rag_context = _fetch_rag_context(
            pa_request.cpt_code,
            pa_request.icd10_codes or [],
        )
        if rag_context:
            nlp_context += f"\n[Relevant Context]\n{rag_context}\n"

        # 4. LLM extraction with enhanced input
        extraction = gemini.extract_clinical_evidence(
            patient_notes=enhanced_text + nlp_context,
            cpt_code=pa_request.cpt_code,
            icd10_codes=pa_request.icd10_codes or [],
        )

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Auto-populate ICD-10 codes from extraction if not user-provided
        extracted_icd = extraction.get("icd10_codes") or []
        if not pa_request.icd10_codes and extracted_icd:
            pa_request.icd10_codes = extracted_icd

        # Auto-populate CPT code from extraction if still PENDING
        suggested_cpt = extraction.get("cpt_code_suggested")
        if pa_request.cpt_code == 'PENDING' and suggested_cpt:
            pa_request.cpt_code = suggested_cpt

        # Auto-populate CPT description if empty
        if not pa_request.cpt_description:
            diag = extraction.get("diagnosis_summary", "")
            if diag and diag.lower() != "no clinical notes available.":
                pa_request.cpt_description = diag[:200]

        # 5. Delete existing evidence (for retries), then persist new evidence
        existing = self.db.execute(
            select(ClinicalEvidence).where(ClinicalEvidence.prior_auth_id == pa_request.id)
        ).scalar_one_or_none()
        if existing:
            self.db.delete(existing)
            self.db.flush()

        evidence = ClinicalEvidence(
            prior_auth_id=pa_request.id,
            diagnosis_summary=extraction.get("diagnosis_summary"),
            medical_necessity_justification=extraction.get("medical_necessity_justification"),
            treatment_history=extraction.get("treatment_history"),
            failed_conservative_therapies=extraction.get("failed_conservative_therapies"),
            supporting_findings=extraction.get("supporting_findings"),
            relevant_lab_results=extraction.get("relevant_lab_results"),
            relevant_imaging=extraction.get("relevant_imaging"),
            medications=extraction.get("medications"),
            source_documents=extraction.get("source_documents"),
            raw_notes_text=notes_text[:50000],
            confidence_score=extraction.get("confidence_score", 0.0),
            extraction_model=self.settings.GEMINI_MODEL,
            extraction_duration_ms=elapsed_ms,
        )
        self.db.add(evidence)
        self.db.flush()

        log_action(
            self.db,
            entity_type="prior_auth_request",
            entity_id=pa_request.id,
            action="clinical_evidence_extracted",
            actor="system:clinical_reader_agent",
            details={
                "confidence_score": evidence.confidence_score,
                "duration_ms": elapsed_ms,
                "model": self.settings.GEMINI_MODEL,
                "nlp_enhanced": bool(nlp_results),
                "rag_enhanced": bool(rag_context),
            },
        )

        logger.info(
            "clinical_reader.done",
            pa_id=str(pa_request.id),
            confidence=evidence.confidence_score,
            duration_ms=elapsed_ms,
            nlp_enhanced=bool(nlp_results),
        )
        return evidence
