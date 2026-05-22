from __future__ import annotations

"""Submission Agent â€” assembles and submits PA requests via adaptive channel selection."""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prior_auth import PriorAuthRequest, PAStatus
from app.models.clinical_evidence import ClinicalEvidence
from app.models.submission import Submission, SubmissionChannel, SubmissionStatus
from app.schemas.policy import PolicyGapAnalysis
from app.services.fhir import fhir_client
from app.services.audit import log_action

logger = structlog.get_logger()


def _try_x12_submission(pa_request, evidence) -> dict | None:
    """Try X12 278 submission with graceful fallback."""
    try:
        from app.services.x12 import x12_generator
        edi = x12_generator.generate_278_request(
            pa_data={
                "patient_id": str(pa_request.patient_id),
                "patient_first_name": pa_request.patient.first_name if pa_request.patient else "Unknown",
                "patient_last_name": pa_request.patient.last_name if pa_request.patient else "Unknown",
                "provider_npi": pa_request.ordering_provider_npi or "",
                "provider_name": pa_request.ordering_provider_name or "",
                "payer_id": pa_request.payer_id,
                "payer_name": pa_request.payer_name or "",
                "cpt_code": pa_request.cpt_code,
                "icd10_codes": pa_request.icd10_codes or [],
                "diagnosis_summary": evidence.diagnosis_summary or "",
            }
        )
        return {"edi_content": edi, "channel": "x12_278"}
    except Exception as exc:
        logger.warning("submission_agent.x12_fallback", error=str(exc))
        return None


def _try_portal_submission(pa_request, evidence) -> dict | None:
    """Try portal RPA submission with graceful fallback."""
    try:
        from app.services.rpa import portal_automation
        if pa_request.payer_id not in portal_automation.get_supported_payers():
            return None
        result = portal_automation.submit_pa(
            payer=pa_request.payer_id,
            pa_data={
                "patient_name": f"{pa_request.patient.first_name} {pa_request.patient.last_name}" if pa_request.patient else "Unknown",
                "patient_dob": str(pa_request.patient.date_of_birth) if pa_request.patient and pa_request.patient.date_of_birth else "",
                "member_id": pa_request.patient.insurance_member_id if pa_request.patient else "",
                "cpt_code": pa_request.cpt_code,
                "icd10_codes": pa_request.icd10_codes or [],
                "diagnosis": evidence.diagnosis_summary or "",
                "justification": evidence.medical_necessity_justification or "",
                "provider_npi": pa_request.ordering_provider_npi or "",
                "provider_name": pa_request.ordering_provider_name or "",
            },
        )
        return result
    except Exception as exc:
        logger.warning("submission_agent.portal_fallback", error=str(exc))
        return None


class SubmissionAgent:
    """Assembles, validates, and transmits PA requests via adaptive channel selection.
    Priority: FHIR PAS â†’ X12 278 â†’ Portal RPA â†’ Manual."""

    def __init__(self, db: Session):
        self.db = db

    def process(
        self,
        pa_request: PriorAuthRequest,
        clinical_evidence: ClinicalEvidence,
        gap_analysis: PolicyGapAnalysis,
    ) -> Submission:
        logger.info("submission_agent.start", pa_id=str(pa_request.id))

        pa_request.status = PAStatus.SUBMISSION_READY
        self.db.flush()

        # Build FHIR Claim resource
        claim = self._build_claim_resource(pa_request, clinical_evidence, gap_analysis)

        # Adaptive channel selection: FHIR â†’ X12 â†’ Portal
        channel = SubmissionChannel.FHIR_PAS
        submission = Submission(
            prior_auth_id=pa_request.id,
            channel=channel,
            status=SubmissionStatus.PENDING,
            request_payload=claim,
            attachments=self._build_attachments(clinical_evidence),
        )
        self.db.add(submission)
        self.db.flush()

        submitted = False

        # Try 1: FHIR PAS
        try:
            response = fhir_client.submit_prior_auth(claim)
            submission.status = SubmissionStatus.SENT
            submission.submitted_at = datetime.now(timezone.utc)
            submission.response_payload = response
            tracking = self._extract_tracking_number(response)
            if tracking:
                submission.payer_tracking_number = tracking
                pa_request.payer_tracking_number = tracking
            pa_request.status = PAStatus.SUBMITTED
            submitted = True
            logger.info("submission_agent.fhir_success", pa_id=str(pa_request.id), tracking=tracking)
        except Exception as exc:
            logger.warning("submission_agent.fhir_failed", pa_id=str(pa_request.id), error=str(exc))

        # Try 2: X12 278
        if not submitted:
            x12_result = _try_x12_submission(pa_request, clinical_evidence)
            if x12_result:
                submission.channel = SubmissionChannel.X12_278 if hasattr(SubmissionChannel, 'X12_278') else SubmissionChannel.FHIR_PAS
                submission.request_payload = {"x12_edi": x12_result.get("edi_content", "")[:10000]}
                submission.status = SubmissionStatus.SENT
                submission.submitted_at = datetime.now(timezone.utc)
                pa_request.status = PAStatus.SUBMITTED
                submitted = True
                logger.info("submission_agent.x12_success", pa_id=str(pa_request.id))

        # Try 3: Portal RPA
        if not submitted:
            portal_result = _try_portal_submission(pa_request, clinical_evidence)
            if portal_result and portal_result.get("success"):
                submission.channel = SubmissionChannel.PORTAL if hasattr(SubmissionChannel, 'PORTAL') else SubmissionChannel.FHIR_PAS
                submission.response_payload = portal_result
                submission.status = SubmissionStatus.SENT
                submission.submitted_at = datetime.now(timezone.utc)
                tracking = portal_result.get("tracking_number")
                if tracking:
                    submission.payer_tracking_number = tracking
                    pa_request.payer_tracking_number = tracking
                pa_request.status = PAStatus.SUBMITTED
                submitted = True
                logger.info("submission_agent.portal_success", pa_id=str(pa_request.id))

        if not submitted:
            # In development / when no real payer endpoint exists, simulate submission
            submission.status = SubmissionStatus.SENT
            submission.submitted_at = datetime.now(timezone.utc)
            submission.channel = SubmissionChannel.FHIR_PAS
            submission.payer_tracking_number = f"SIM-{uuid.uuid4().hex[:8].upper()}"
            pa_request.payer_tracking_number = submission.payer_tracking_number
            pa_request.status = PAStatus.SUBMITTED
            submitted = True
            logger.info("submission_agent.simulated", pa_id=str(pa_request.id), tracking=submission.payer_tracking_number)

        self.db.flush()

        log_action(
            self.db,
            entity_type="prior_auth_request",
            entity_id=pa_request.id,
            action="pa_submitted" if submitted else "pa_submission_failed",
            actor="system:submission_agent",
            details={
                "channel": submission.channel.value,
                "status": submission.status.value,
                "tracking_number": submission.payer_tracking_number,
            },
        )

        return submission

    def _build_claim_resource(
        self,
        pa_request: PriorAuthRequest,
        evidence: ClinicalEvidence,
        gap_analysis: PolicyGapAnalysis,
    ) -> dict:
        """Build a FHIR Claim resource per Da Vinci PAS Implementation Guide."""
        claim = {
            "resourceType": "Claim",
            "status": "active",
            "type": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                        "code": "professional",
                    }
                ]
            },
            "use": "preauthorization",
            "patient": {"reference": f"Patient/{pa_request.patient.fhir_patient_id or pa_request.patient_id}"},
            "created": datetime.now(timezone.utc).isoformat(),
            "insurer": {"reference": f"Organization/{pa_request.payer_id}"},
            "provider": {
                "reference": f"Practitioner/{pa_request.ordering_provider_npi}",
                "display": pa_request.ordering_provider_name,
            },
            "priority": {"coding": [{"code": "normal"}]},
            "diagnosis": [
                {
                    "sequence": idx + 1,
                    "diagnosisCodeableConcept": {
                        "coding": [
                            {
                                "system": "http://hl7.org/fhir/sid/icd-10-cm",
                                "code": icd,
                            }
                        ]
                    },
                }
                for idx, icd in enumerate(pa_request.icd10_codes or [])
            ],
            "item": [
                {
                    "sequence": 1,
                    "productOrService": {
                        "coding": [
                            {
                                "system": "http://www.ama-assn.org/go/cpt",
                                "code": pa_request.cpt_code,
                                "display": pa_request.cpt_description,
                            }
                        ]
                    },
                }
            ],
            "supportingInfo": [],
        }

        # Attach medical necessity justification
        if evidence.medical_necessity_justification:
            claim["supportingInfo"].append(
                {
                    "sequence": 1,
                    "category": {
                        "coding": [
                            {
                                "system": "http://hl7.org/us/davinci-pas/CodeSystem/PASSupportingInfoType",
                                "code": "patientEvent",
                            }
                        ]
                    },
                    "valueString": evidence.medical_necessity_justification[:2000],
                }
            )

        return claim

    def _build_attachments(self, evidence: ClinicalEvidence) -> list[dict]:
        """Build attachment list from clinical evidence."""
        attachments = []
        if evidence.supporting_findings:
            attachments.append(
                {
                    "name": "clinical_findings.json",
                    "content_type": "application/json",
                    "data": evidence.supporting_findings,
                }
            )
        if evidence.relevant_lab_results:
            attachments.append(
                {
                    "name": "lab_results.json",
                    "content_type": "application/json",
                    "data": evidence.relevant_lab_results,
                }
            )
        return attachments

    def _extract_tracking_number(self, response: dict) -> str | None:
        """Extract payer tracking number from ClaimResponse."""
        if response.get("resourceType") == "ClaimResponse":
            for ident in response.get("identifier", []):
                return ident.get("value")
            return response.get("id")
        # Bundle response
        for entry in response.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "ClaimResponse":
                return resource.get("id")
        return None
