from __future__ import annotations

"""Policy Agent â€” retrieves payer criteria, runs rules engine, and performs gap analysis."""

import uuid
import structlog

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.policy import PayerPolicy, PolicyCriterion
from app.models.prior_auth import PriorAuthRequest, PAStatus
from app.models.clinical_evidence import ClinicalEvidence
from app.schemas.policy import PolicyGapAnalysis, CriterionResult
from app.services import gemini
from app.services.audit import log_action
from app.config import get_settings

logger = structlog.get_logger()


def _run_rules_engine(criteria_dicts: list[dict], evidence_dict: dict) -> dict | None:
    """Run deterministic rules engine with graceful fallback."""
    try:
        from app.services.rules_engine import rules_engine
        decision = rules_engine.evaluate_criteria(criteria_dicts, evidence_dict)
        return {
            "recommendation": decision.recommendation,
            "confidence": decision.confidence,
            "overall_met": decision.overall_met,
            "results": [
                {
                    "criterion_code": r.criterion_code,
                    "is_met": r.is_met,
                    "confidence": r.confidence,
                    "reason": r.reason,
                }
                for r in decision.results
            ],
            "trace": decision.trace,
        }
    except Exception as exc:
        logger.warning("policy_agent.rules_engine_fallback", error=str(exc))
        return None


class PolicyAgent:
    """Retrieves payer-specific PA policies and performs gap analysis.
    Enhanced with deterministic rules engine pre-check before LLM analysis."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def process(
        self, pa_request: PriorAuthRequest, clinical_evidence: ClinicalEvidence
    ) -> PolicyGapAnalysis:
        logger.info("policy_agent.start", pa_id=str(pa_request.id), payer=pa_request.payer_id)

        pa_request.status = PAStatus.POLICY_CHECK
        self.db.flush()

        # 1. Fetch policy + criteria from DB
        policy = self._get_policy(pa_request.payer_id, pa_request.cpt_code)
        criteria = self._get_criteria(policy.id) if policy else []

        criteria_dicts = [
            {
                "criterion_code": c.criterion_code,
                "description": c.description,
                "criterion_type": c.criterion_type,
                "is_mandatory": c.is_mandatory,
            }
            for c in criteria
        ]

        if not policy:
            logger.warning("policy_agent.no_policy_found", payer=pa_request.payer_id, cpt=pa_request.cpt_code)
            # Use clinical evidence confidence as fallback when no policy exists
            fallback_confidence = clinical_evidence.confidence_score or 0.0
            rec = "approve" if fallback_confidence >= self.settings.CONFIDENCE_THRESHOLD else "needs_review"
            return PolicyGapAnalysis(
                prior_auth_id=pa_request.id,
                payer_id=pa_request.payer_id,
                cpt_code=pa_request.cpt_code,
                pa_required=True,
                criteria_results=[],
                all_mandatory_met=fallback_confidence >= self.settings.CONFIDENCE_THRESHOLD,
                overall_confidence=fallback_confidence,
                recommendation=rec,
                gap_summary="No specific policy criteria found for this payer/CPT combination. Using clinical evidence confidence.",
            )

        # 2. Build evidence dict
        evidence_dict = {
            "diagnosis_summary": clinical_evidence.diagnosis_summary,
            "medical_necessity_justification": clinical_evidence.medical_necessity_justification,
            "treatment_history": clinical_evidence.treatment_history,
            "failed_conservative_therapies": clinical_evidence.failed_conservative_therapies,
            "supporting_findings": clinical_evidence.supporting_findings,
            "relevant_lab_results": clinical_evidence.relevant_lab_results,
            "medications": clinical_evidence.medications,
        }

        # 3. Run deterministic rules engine first
        rules_result = _run_rules_engine(criteria_dicts, evidence_dict)
        rules_context = ""
        if rules_result:
            rules_context = (
                f"\n[Rules Engine Pre-check]\n"
                f"Recommendation: {rules_result['recommendation']}\n"
                f"Confidence: {rules_result['confidence']:.2f}\n"
                f"Criteria met: {sum(1 for r in rules_result['results'] if r['is_met'])}/{len(rules_result['results'])}\n"
            )
            for r in rules_result["results"]:
                status = "MET" if r["is_met"] else "NOT MET"
                rules_context += f"  - {r['criterion_code']}: {status} ({r['reason']})\n"

        # 4. LLM gap analysis (with rules engine context)
        analysis = gemini.analyze_policy_gap(
            clinical_evidence=evidence_dict,
            policy_criteria=criteria_dicts,
            payer_name=pa_request.payer_name or pa_request.payer_id,
            cpt_code=pa_request.cpt_code,
        )

        # 5. Build result â€” blend rules engine + LLM
        criteria_results = [
            CriterionResult(
                criterion_code=cr.get("criterion_code", ""),
                description=cr.get("description", ""),
                is_met=cr.get("is_met", False),
                evidence_citation=cr.get("evidence_citation"),
                confidence=cr.get("confidence", 0.0),
            )
            for cr in analysis.get("criteria_results", [])
        ]

        # If rules engine was decisive (high confidence), blend its confidence
        llm_confidence = analysis.get("overall_confidence", 0.0)
        if rules_result and rules_result["confidence"] > 0.8:
            blended_confidence = (rules_result["confidence"] * 0.4) + (llm_confidence * 0.6)
        else:
            blended_confidence = llm_confidence

        gap_analysis = PolicyGapAnalysis(
            prior_auth_id=pa_request.id,
            payer_id=pa_request.payer_id,
            cpt_code=pa_request.cpt_code,
            pa_required=policy.pa_required,
            criteria_results=criteria_results,
            all_mandatory_met=analysis.get("all_mandatory_met", False),
            overall_confidence=blended_confidence,
            recommendation=analysis.get("recommendation", "needs_review"),
            gap_summary=analysis.get("gap_summary"),
        )

        pa_request.confidence_score = gap_analysis.overall_confidence
        self.db.flush()

        log_action(
            self.db,
            entity_type="prior_auth_request",
            entity_id=pa_request.id,
            action="policy_gap_analysis_completed",
            actor="system:policy_agent",
            details={
                "recommendation": gap_analysis.recommendation,
                "overall_confidence": gap_analysis.overall_confidence,
                "all_mandatory_met": gap_analysis.all_mandatory_met,
                "criteria_count": len(criteria_results),
                "rules_engine_used": rules_result is not None,
                "rules_confidence": rules_result["confidence"] if rules_result else None,
            },
        )

        logger.info(
            "policy_agent.done",
            pa_id=str(pa_request.id),
            recommendation=gap_analysis.recommendation,
            confidence=gap_analysis.overall_confidence,
            rules_engine_used=rules_result is not None,
        )
        return gap_analysis

    def _get_policy(self, payer_id: str, cpt_code: str) -> PayerPolicy | None:
        result = self.db.execute(
            select(PayerPolicy).where(
                PayerPolicy.payer_id == payer_id,
                PayerPolicy.cpt_code == cpt_code,
            )
        )
        return result.scalar_one_or_none()

    def _get_criteria(self, policy_id: uuid.UUID) -> list[PolicyCriterion]:
        result = self.db.execute(
            select(PolicyCriterion).where(PolicyCriterion.policy_id == policy_id)
        )
        return list(result.scalars().all())
