from __future__ import annotations

"""Orchestrator -- coordinates the full PA workflow with optional Celery dispatch."""

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.prior_auth import PriorAuthRequest, PAStatus
from app.models.clinical_evidence import ClinicalEvidence
from app.agents.clinical_reader import ClinicalReaderAgent
from app.agents.policy_agent import PolicyAgent
from app.agents.submission_agent import SubmissionAgent
from app.agents.appeal_agent import AppealAgent
from app.schemas.policy import PolicyGapAnalysis
from app.services.audit import log_action
from app.services.sse import emit as sse_emit
from app.services.notifications import notify_decision
from app.config import get_settings

logger = structlog.get_logger()


def _try_celery_dispatch(pa_id, clinical_notes: str | None) -> bool:
    """Try to dispatch to Celery. Returns True if dispatched."""
    try:
        from app.services.tasks import run_pipeline_task
        from app.services.celery_app import get_celery_app
        celery_app = get_celery_app()
        if celery_app is None:
            return False
        run_pipeline_task.delay(str(pa_id), clinical_notes)
        logger.info('orchestrator.celery_dispatched', pa_id=str(pa_id))
        return True
    except Exception as exc:
        logger.warning('orchestrator.celery_fallback', error=str(exc))
        return False


class Orchestrator:
    """
    Coordinates the end-to-end PA workflow:
    INITIATED -> CLINICAL_REVIEW -> POLICY_CHECK -> SUBMISSION -> PENDING_DECISION
    If denied: -> APPEAL -> (approve / escalate)
    """

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.clinical_reader = ClinicalReaderAgent(db)
        self.policy_agent = PolicyAgent(db)
        self.submission_agent = SubmissionAgent(db)
        self.appeal_agent = AppealAgent(db)

    def run_full_pipeline(
        self,
        pa_request: PriorAuthRequest,
        clinical_notes: str | None = None,
    ) -> dict:
        """Execute the complete PA pipeline. Returns a status summary dict."""
        logger.info('orchestrator.pipeline_start', pa_id=str(pa_request.id))

        result = {
            'prior_auth_id': str(pa_request.id),
            'status': None,
            'clinical_evidence_id': None,
            'gap_analysis': None,
            'submission_id': None,
            'requires_human_review': False,
            'human_review_reason': None,
        }

        try:
            # Step 1: Clinical evidence extraction
            sse_emit(str(pa_request.id), 'step', {'status': 'initiated', 'step': 'clinical_reader', 'message': 'Reading clinical records...'})
            evidence = self.clinical_reader.process(pa_request, clinical_notes)
            result['clinical_evidence_id'] = str(evidence.id)
            sse_emit(str(pa_request.id), 'step', {'status': 'clinical_review', 'step': 'clinical_reader', 'message': 'Clinical evidence extracted', 'done': True})

            # Step 2: Policy gap analysis
            sse_emit(str(pa_request.id), 'step', {'status': 'clinical_review', 'step': 'policy_agent', 'message': 'Checking payer policy rules...'})
            gap_analysis = self.policy_agent.process(pa_request, evidence)
            sse_emit(str(pa_request.id), 'step', {'status': 'policy_check', 'step': 'policy_agent', 'message': f'Policy check complete — {gap_analysis.recommendation}', 'done': True})
            result['gap_analysis'] = {
                'recommendation': gap_analysis.recommendation,
                'confidence': gap_analysis.overall_confidence,
                'all_mandatory_met': gap_analysis.all_mandatory_met,
                'criteria_count': len(gap_analysis.criteria_results),
            }

            # Decision gate
            if gap_analysis.recommendation == 'deny':
                pa_request.status = PAStatus.DENIED
                pa_request.decision_reason = gap_analysis.gap_summary
                result['status'] = PAStatus.DENIED.value
                logger.info('orchestrator.pre_denial', pa_id=str(pa_request.id))
                self.db.flush()
                return result

            if gap_analysis.recommendation == 'needs_review':
                pa_request.requires_human_review = True
                gap_detail = gap_analysis.gap_summary or 'Some policy criteria could not be fully verified.'
                pa_request.human_review_reason = (
                    f'The AI could not fully confirm all requirements for this request. {gap_detail} '
                    f'A reviewer should verify the clinical documentation before proceeding.'
                )
                result['requires_human_review'] = True
                result['human_review_reason'] = pa_request.human_review_reason

            # Confidence gate
            if gap_analysis.overall_confidence < self.settings.CONFIDENCE_THRESHOLD:
                pa_request.requires_human_review = True
                if gap_analysis.overall_confidence < 0.2:
                    reason_text = (
                        'The uploaded documents do not appear to contain sufficient medical information '
                        'to support this prior authorization request. Please verify the documents are '
                        'valid medical records and contain relevant clinical details.'
                    )
                elif gap_analysis.overall_confidence < 0.5:
                    reason_text = (
                        'The clinical documentation provides limited support for this request. '
                        'Some key medical details may be missing or unclear. '
                        'A reviewer should check if additional records are needed.'
                    )
                else:
                    reason_text = (
                        'The clinical documentation partially supports this request but falls short '
                        'of full automated approval. A brief manual review is recommended.'
                    )
                pa_request.human_review_reason = reason_text
                result['requires_human_review'] = True
                result['human_review_reason'] = pa_request.human_review_reason

            # Step 3: Submit
            sse_emit(str(pa_request.id), 'step', {'status': 'submission_ready', 'step': 'submission_agent', 'message': 'Preparing submission...'})
            submission = self.submission_agent.process(pa_request, evidence, gap_analysis)
            result['submission_id'] = str(submission.id)
            sse_emit(str(pa_request.id), 'step', {'status': 'submitted', 'step': 'submission_agent', 'message': 'Submission complete', 'done': True})

            # Auto-decide: in demo mode (no real payer), finalize based on AI confidence
            from datetime import datetime, timezone
            if gap_analysis.recommendation == 'approve' and gap_analysis.overall_confidence >= 0.8 and not pa_request.requires_human_review:
                pa_request.status = PAStatus.APPROVED
                pa_request.confidence_score = gap_analysis.overall_confidence
                pa_request.decision_reason = (
                    f"Auto-approved: AI confidence {gap_analysis.overall_confidence:.0%}. "
                    f"All policy criteria met."
                )
                pa_request.decision_date = datetime.now(timezone.utc)
                logger.info('orchestrator.auto_approved', pa_id=str(pa_request.id), confidence=gap_analysis.overall_confidence)
            elif gap_analysis.recommendation == 'approve':
                pa_request.status = PAStatus.PENDING_DECISION
                pa_request.confidence_score = gap_analysis.overall_confidence
            else:
                pa_request.confidence_score = gap_analysis.overall_confidence

            result['status'] = pa_request.status.value

            self.db.commit()

            # Notify patient of decision
            try:
                patient = pa_request.patient
                if patient and patient.email:
                    notify_decision(
                        patient.email,
                        f"{patient.first_name} {patient.last_name}",
                        pa_request.status.value,
                        pa_request.decision_reason or '',
                    )
            except Exception:
                logger.warning('orchestrator.notification_failed', pa_id=str(pa_request.id))

            sse_emit(str(pa_request.id), 'pipeline_complete', {'status': pa_request.status.value, 'confidence': pa_request.confidence_score})
            logger.info('orchestrator.pipeline_complete', pa_id=str(pa_request.id), status=pa_request.status.value)

        except Exception as exc:
            self.db.rollback()
            logger.error('orchestrator.pipeline_error', pa_id=str(pa_request.id), error=str(exc))
            pa_request.status = PAStatus.ESCALATED
            pa_request.requires_human_review = True
            pa_request.human_review_reason = (
                'An error occurred while processing this request. '
                'Please review the documentation manually and retry if needed.'
            )
            self.db.commit()
            sse_emit(str(pa_request.id), 'pipeline_complete', {'status': 'escalated', 'error': str(exc)})
            result['status'] = PAStatus.ESCALATED.value
            result['requires_human_review'] = True
            result['human_review_reason'] = pa_request.human_review_reason
            raise

        return result

    def handle_denial(
        self,
        pa_request: PriorAuthRequest,
        denial_reason: str,
        denial_details: str,
        denial_code: str | None = None,
    ) -> dict:
        """Handle a denial notification -- trigger appeal agent."""
        logger.info('orchestrator.handle_denial', pa_id=str(pa_request.id))

        pa_request.status = PAStatus.DENIED
        pa_request.decision_reason = denial_details
        self.db.flush()

        # Fetch clinical evidence
        evidence_result = self.db.execute(
            select(ClinicalEvidence).where(ClinicalEvidence.prior_auth_id == pa_request.id)
        )
        evidence = evidence_result.scalar_one_or_none()

        if not evidence:
            logger.error('orchestrator.no_evidence_for_appeal', pa_id=str(pa_request.id))
            pa_request.status = PAStatus.ESCALATED
            pa_request.requires_human_review = True
            pa_request.human_review_reason = 'No clinical evidence found for appeal.'
            self.db.commit()
            return {'status': 'escalated', 'reason': 'No clinical evidence available'}

        appeal = self.appeal_agent.process(
            pa_request, evidence, denial_reason, denial_details, denial_code
        )

        self.db.commit()

        return {
            'prior_auth_id': str(pa_request.id),
            'appeal_id': str(appeal.id),
            'appeal_status': appeal.status.value,
            'attempt_number': appeal.attempt_number,
            'requires_human_review': pa_request.requires_human_review,
        }
