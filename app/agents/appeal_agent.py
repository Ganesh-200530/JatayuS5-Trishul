from __future__ import annotations

"""Appeal Agent â€” handles denials with RAG-enhanced evidence and appeal letter generation."""

import uuid
import structlog
from datetime import datetime, timezone

from sqlalchemy import select, func as sa_func
from sqlalchemy.orm import Session

from app.models.prior_auth import PriorAuthRequest, PAStatus
from app.models.clinical_evidence import ClinicalEvidence
from app.models.appeal import Appeal, AppealStatus, DenialReason
from app.services import gemini
from app.services.audit import log_action
from app.config import get_settings

logger = structlog.get_logger()

MAX_AUTO_APPEALS = 2


def _fetch_appeal_rag_context(cpt_code: str, denial_reason: str, icd_codes: list[str]) -> str:
    """Fetch RAG context for appeal with graceful fallback."""
    try:
        from app.services.rag import retrieve_context_for_appeal
        return retrieve_context_for_appeal(cpt_code, denial_reason, icd_codes)
    except Exception as exc:
        logger.warning("appeal_agent.rag_fallback", error=str(exc))
        return ""


class AppealAgent:
    """Autonomously drafts and submits appeal letters for denied PA requests.
    Enhanced with RAG-based medical literature retrieval for stronger appeals."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def process(
        self,
        pa_request: PriorAuthRequest,
        clinical_evidence: ClinicalEvidence,
        denial_reason: str,
        denial_details: str,
        denial_code: str | None = None,
    ) -> Appeal:
        logger.info("appeal_agent.start", pa_id=str(pa_request.id), denial=denial_reason)

        pa_request.status = PAStatus.APPEAL_IN_PROGRESS
        self.db.flush()

        attempt_count = self._get_attempt_count(pa_request.id)
        attempt_number = attempt_count + 1

        if attempt_number > MAX_AUTO_APPEALS:
            return self._escalate(pa_request, denial_reason, denial_details, attempt_number)

        classified_reason = self._classify_denial(denial_reason)

        evidence_dict = {
            "diagnosis_summary": clinical_evidence.diagnosis_summary,
            "medical_necessity_justification": clinical_evidence.medical_necessity_justification,
            "treatment_history": clinical_evidence.treatment_history,
            "failed_conservative_therapies": clinical_evidence.failed_conservative_therapies,
            "supporting_findings": clinical_evidence.supporting_findings,
            "relevant_lab_results": clinical_evidence.relevant_lab_results,
            "relevant_imaging": clinical_evidence.relevant_imaging,
            "medications": clinical_evidence.medications,
        }

        patient = pa_request.patient
        patient_summary = f"{patient.first_name} {patient.last_name}, DOB: {patient.date_of_birth}, MRN: {patient.mrn}"

        # RAG: fetch medical literature and precedent context
        rag_context = _fetch_appeal_rag_context(
            pa_request.cpt_code,
            denial_reason,
            pa_request.icd10_codes or [],
        )
        if rag_context:
            evidence_dict["rag_literature_context"] = rag_context

        # Generate appeal via Gemini (with RAG-enhanced evidence)
        appeal_data = gemini.generate_appeal_letter(
            denial_reason=denial_reason,
            denial_details=denial_details,
            clinical_evidence=evidence_dict,
            policy_criteria=[],
            patient_summary=patient_summary,
            cpt_code=pa_request.cpt_code,
            payer_name=pa_request.payer_name or pa_request.payer_id,
        )

        appeal = Appeal(
            prior_auth_id=pa_request.id,
            attempt_number=attempt_number,
            status=AppealStatus.READY,
            denial_reason=classified_reason,
            denial_details=denial_details,
            denial_code=denial_code,
            appeal_letter=appeal_data.get("appeal_letter"),
            additional_evidence=appeal_data.get("additional_evidence_needed"),
            cited_references=appeal_data.get("cited_references"),
        )
        self.db.add(appeal)
        self.db.flush()

        confidence = appeal_data.get("confidence_of_success", 0.0)
        if confidence < self.settings.CONFIDENCE_THRESHOLD:
            pa_request.requires_human_review = True
            pa_request.human_review_reason = (
                f"Appeal confidence {confidence:.2f} below threshold. "
                f"Denial: {denial_reason}. Attempt #{attempt_number}."
            )

        log_action(
            self.db,
            entity_type="prior_auth_request",
            entity_id=pa_request.id,
            action="appeal_drafted",
            actor="system:appeal_agent",
            details={
                "attempt_number": attempt_number,
                "denial_reason": denial_reason,
                "confidence_of_success": confidence,
                "classified_as": classified_reason.value if classified_reason else None,
                "rag_enhanced": bool(rag_context),
            },
        )

        self.db.flush()
        logger.info(
            "appeal_agent.done",
            pa_id=str(pa_request.id),
            attempt=attempt_number,
            confidence=confidence,
            rag_enhanced=bool(rag_context),
        )
        return appeal

    def _escalate(
        self, pa_request: PriorAuthRequest, denial_reason: str, denial_details: str, attempt: int
    ) -> Appeal:
        """Escalate to human review after max auto-appeal attempts."""
        logger.info("appeal_agent.escalating", pa_id=str(pa_request.id), attempt=attempt)

        pa_request.status = PAStatus.ESCALATED
        pa_request.requires_human_review = True
        pa_request.human_review_reason = (
            f"Max auto-appeal attempts ({MAX_AUTO_APPEALS}) reached. "
            f"Denial: {denial_reason}. Requires peer-to-peer or manual intervention."
        )

        appeal = Appeal(
            prior_auth_id=pa_request.id,
            attempt_number=attempt,
            status=AppealStatus.ESCALATED,
            denial_reason=self._classify_denial(denial_reason),
            denial_details=denial_details,
        )
        self.db.add(appeal)

        log_action(
            self.db,
            entity_type="prior_auth_request",
            entity_id=pa_request.id,
            action="appeal_escalated_to_human",
            actor="system:appeal_agent",
            details={"attempt_number": attempt, "denial_reason": denial_reason},
        )

        self.db.flush()
        return appeal

    def _get_attempt_count(self, pa_id: uuid.UUID) -> int:
        import uuid as _uuid  # already imported at module level via models

        result = self.db.execute(
            select(sa_func.count(Appeal.id)).where(Appeal.prior_auth_id == pa_id)
        )
        return result.scalar_one()

    @staticmethod
    def _classify_denial(reason: str) -> DenialReason:
        reason_lower = reason.lower()
        if "missing" in reason_lower or "incomplete" in reason_lower or "additional" in reason_lower:
            return DenialReason.MISSING_INFO
        if "medical necessity" in reason_lower or "not medically" in reason_lower:
            return DenialReason.MEDICAL_NECESSITY
        if "network" in reason_lower:
            return DenialReason.OUT_OF_NETWORK
        if "code" in reason_lower or "coding" in reason_lower or "cpt" in reason_lower:
            return DenialReason.CODING_ERROR
        if "duplicate" in reason_lower:
            return DenialReason.DUPLICATE
        if "admin" in reason_lower or "timely" in reason_lower:
            return DenialReason.ADMINISTRATIVE
        return DenialReason.OTHER
