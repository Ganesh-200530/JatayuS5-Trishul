from __future__ import annotations

"""Deterministic Rules Engine for payer criteria evaluation.

Evaluates policy criteria using structured rules BEFORE LLM analysis.
Provides explainable, auditable policy matching with full decision trace.
"""

import re
import json
import structlog
from typing import Any
from datetime import datetime, timedelta

logger = structlog.get_logger()


class RuleResult:
    """Result of evaluating a single policy criterion."""

    def __init__(
        self,
        criterion_code: str,
        description: str,
        is_met: bool,
        evidence: str | None = None,
        rule_trace: str = "",
        confidence: float = 1.0,
        is_mandatory: bool = True,
    ):
        self.criterion_code = criterion_code
        self.description = description
        self.is_met = is_met
        self.evidence = evidence
        self.rule_trace = rule_trace
        self.confidence = confidence
        self.is_mandatory = is_mandatory

    def to_dict(self) -> dict:
        return {
            "criterion_code": self.criterion_code,
            "description": self.description,
            "is_met": self.is_met,
            "evidence": self.evidence,
            "rule_trace": self.rule_trace,
            "confidence": self.confidence,
            "is_mandatory": self.is_mandatory,
        }


class PolicyDecision:
    """Aggregate decision from the rules engine."""

    def __init__(
        self,
        pa_required: bool,
        recommendation: str,
        criteria_results: list[RuleResult],
        overall_confidence: float,
        decision_trace: list[str],
    ):
        self.pa_required = pa_required
        self.recommendation = recommendation
        self.criteria_results = criteria_results
        self.overall_confidence = overall_confidence
        self.decision_trace = decision_trace
        self.all_mandatory_met = all(
            r.is_met for r in criteria_results if r.is_mandatory
        )

    def to_dict(self) -> dict:
        return {
            "pa_required": self.pa_required,
            "recommendation": self.recommendation,
            "all_mandatory_met": self.all_mandatory_met,
            "overall_confidence": self.overall_confidence,
            "criteria_results": [r.to_dict() for r in self.criteria_results],
            "decision_trace": self.decision_trace,
        }


class RulesEngine:
    """
    Deterministic policy criteria evaluation engine.

    Supports evaluation_logic JSON rules:
    {
        "type": "icd10_match" | "cpt_match" | "lab_threshold" | "medication_trial" |
                "therapy_failure" | "age_range" | "diagnosis_present" | "imaging_required" |
                "time_constraint" | "composite",
        "params": { ... type-specific parameters ... }
    }
    """

    def __init__(self):
        self._evaluators = {
            "icd10_match": self._eval_icd10_match,
            "cpt_match": self._eval_cpt_match,
            "lab_threshold": self._eval_lab_threshold,
            "medication_trial": self._eval_medication_trial,
            "therapy_failure": self._eval_therapy_failure,
            "age_range": self._eval_age_range,
            "diagnosis_present": self._eval_diagnosis_present,
            "imaging_required": self._eval_imaging_required,
            "time_constraint": self._eval_time_constraint,
            "composite": self._eval_composite,
        }

    def evaluate_criteria(
        self,
        criteria: list[dict],
        clinical_evidence: dict,
        patient_data: dict,
        pa_request: dict,
    ) -> PolicyDecision:
        """
        Evaluate all policy criteria against clinical evidence.

        Args:
            criteria: List of PolicyCriterion dicts with evaluation_logic
            clinical_evidence: Extracted clinical evidence dict
            patient_data: Patient demographics
            pa_request: PA request details (cpt_code, icd10_codes, etc.)
        """
        results: list[RuleResult] = []
        decision_trace: list[str] = []

        context = {
            "evidence": clinical_evidence,
            "patient": patient_data,
            "request": pa_request,
        }

        for criterion in criteria:
            logic = criterion.get("evaluation_logic")
            code = criterion.get("criterion_code", "UNKNOWN")
            desc = criterion.get("description", "")
            mandatory = criterion.get("is_mandatory", True)

            if not logic:
                # No evaluation logic — needs LLM review
                results.append(RuleResult(
                    criterion_code=code,
                    description=desc,
                    is_met=False,
                    rule_trace="No evaluation_logic defined — requires LLM analysis",
                    confidence=0.0,
                    is_mandatory=mandatory,
                ))
                decision_trace.append(f"[{code}] No rules defined, deferred to LLM")
                continue

            rule_type = logic.get("type", "")
            params = logic.get("params", {})

            evaluator = self._evaluators.get(rule_type)
            if not evaluator:
                results.append(RuleResult(
                    criterion_code=code,
                    description=desc,
                    is_met=False,
                    rule_trace=f"Unknown rule type: {rule_type}",
                    confidence=0.0,
                    is_mandatory=mandatory,
                ))
                decision_trace.append(f"[{code}] Unknown rule type '{rule_type}'")
                continue

            try:
                result = evaluator(code, desc, params, context, mandatory)
                results.append(result)
                status = "MET" if result.is_met else "NOT MET"
                decision_trace.append(
                    f"[{code}] {status} (conf={result.confidence:.2f}) — {result.rule_trace}"
                )
            except Exception as exc:
                results.append(RuleResult(
                    criterion_code=code,
                    description=desc,
                    is_met=False,
                    rule_trace=f"Evaluation error: {str(exc)}",
                    confidence=0.0,
                    is_mandatory=mandatory,
                ))
                decision_trace.append(f"[{code}] ERROR: {str(exc)}")

        # Compute overall decision
        mandatory_results = [r for r in results if r.is_mandatory]
        all_mandatory_met = all(r.is_met for r in mandatory_results) if mandatory_results else False

        if not results:
            recommendation = "needs_review"
            overall_confidence = 0.0
        elif all_mandatory_met:
            recommendation = "approve"
            overall_confidence = (
                sum(r.confidence for r in results) / len(results) if results else 0.0
            )
        elif any(r.confidence == 0.0 for r in mandatory_results if not r.is_met):
            recommendation = "needs_review"
            overall_confidence = sum(r.confidence for r in results) / len(results)
        else:
            recommendation = "deny"
            overall_confidence = sum(r.confidence for r in results) / len(results)

        decision_trace.append(
            f"\nFINAL: recommendation={recommendation}, "
            f"all_mandatory_met={all_mandatory_met}, "
            f"confidence={overall_confidence:.2f}"
        )

        return PolicyDecision(
            pa_required=True,
            recommendation=recommendation,
            criteria_results=results,
            overall_confidence=overall_confidence,
            decision_trace=decision_trace,
        )

    # ── Rule Evaluators ──────────────────────────────────

    def _eval_icd10_match(
        self, code: str, desc: str, params: dict, ctx: dict, mandatory: bool
    ) -> RuleResult:
        """Check if required ICD-10 codes are present."""
        required_codes = params.get("codes", [])
        match_type = params.get("match", "any")  # "any" or "all"
        request_codes = ctx["request"].get("icd10_codes", [])

        matched = [c for c in required_codes if any(rc.startswith(c) for rc in request_codes)]

        if match_type == "all":
            is_met = len(matched) == len(required_codes)
        else:
            is_met = len(matched) > 0

        return RuleResult(
            criterion_code=code, description=desc, is_met=is_met,
            evidence=f"Matched codes: {matched}" if matched else "No matching ICD-10 codes found",
            rule_trace=f"icd10_match({match_type}): required={required_codes}, found={request_codes}, matched={matched}",
            confidence=1.0, is_mandatory=mandatory,
        )

    def _eval_cpt_match(
        self, code: str, desc: str, params: dict, ctx: dict, mandatory: bool
    ) -> RuleResult:
        """Check if the CPT code matches allowed codes."""
        allowed = params.get("codes", [])
        request_cpt = ctx["request"].get("cpt_code", "")
        is_met = request_cpt in allowed

        return RuleResult(
            criterion_code=code, description=desc, is_met=is_met,
            evidence=f"CPT {request_cpt} {'in' if is_met else 'not in'} allowed list",
            rule_trace=f"cpt_match: requested={request_cpt}, allowed={allowed}",
            confidence=1.0, is_mandatory=mandatory,
        )

    def _eval_lab_threshold(
        self, code: str, desc: str, params: dict, ctx: dict, mandatory: bool
    ) -> RuleResult:
        """Check if a lab result meets a threshold (e.g., HbA1c > 7.0)."""
        lab_name = params.get("lab_name", "").lower()
        operator = params.get("operator", ">")  # >, <, >=, <=, ==
        threshold = params.get("threshold", 0)

        lab_results = ctx["evidence"].get("relevant_lab_results") or []
        matched_value = None
        for lab in lab_results:
            test_name = (lab.get("test") or lab.get("name") or "").lower()
            if lab_name in test_name:
                try:
                    val_str = str(lab.get("value", ""))
                    matched_value = float(re.search(r"[\d.]+", val_str).group())
                except (AttributeError, ValueError):
                    continue
                break

        if matched_value is None:
            return RuleResult(
                criterion_code=code, description=desc, is_met=False,
                evidence=f"Lab '{lab_name}' not found in evidence",
                rule_trace=f"lab_threshold: {lab_name} {operator} {threshold} — lab not found",
                confidence=0.5, is_mandatory=mandatory,
            )

        ops = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
               ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
               "==": lambda a, b: a == b}
        is_met = ops.get(operator, lambda a, b: False)(matched_value, threshold)

        return RuleResult(
            criterion_code=code, description=desc, is_met=is_met,
            evidence=f"{lab_name}={matched_value} {operator} {threshold}",
            rule_trace=f"lab_threshold: {matched_value} {operator} {threshold} → {is_met}",
            confidence=1.0, is_mandatory=mandatory,
        )

    def _eval_medication_trial(
        self, code: str, desc: str, params: dict, ctx: dict, mandatory: bool
    ) -> RuleResult:
        """Check if patient has tried required medications."""
        required_meds = [m.lower() for m in params.get("medications", [])]
        min_trials = params.get("min_trials", 1)

        evidence_meds = ctx["evidence"].get("medications") or []
        failed_therapies = ctx["evidence"].get("failed_conservative_therapies") or []

        tried = []
        for med in evidence_meds:
            med_name = (med.get("name") or "").lower()
            for req in required_meds:
                if req in med_name:
                    tried.append(req)

        for therapy in failed_therapies:
            therapy_lower = therapy.lower() if isinstance(therapy, str) else ""
            for req in required_meds:
                if req in therapy_lower and req not in tried:
                    tried.append(req)

        is_met = len(tried) >= min_trials

        return RuleResult(
            criterion_code=code, description=desc, is_met=is_met,
            evidence=f"Tried {len(tried)}/{min_trials} required medications: {tried}",
            rule_trace=f"medication_trial: required={required_meds}, min={min_trials}, found={tried}",
            confidence=1.0 if tried else 0.5, is_mandatory=mandatory,
        )

    def _eval_therapy_failure(
        self, code: str, desc: str, params: dict, ctx: dict, mandatory: bool
    ) -> RuleResult:
        """Check if conservative therapies have been tried and failed."""
        required_therapies = [t.lower() for t in params.get("therapies", [])]
        min_failures = params.get("min_failures", 1)

        failed = ctx["evidence"].get("failed_conservative_therapies") or []
        treatment_history = ctx["evidence"].get("treatment_history") or []

        matched = []
        for therapy in failed:
            therapy_lower = therapy.lower() if isinstance(therapy, str) else ""
            for req in required_therapies:
                if req in therapy_lower:
                    matched.append(req)

        for tx in treatment_history:
            outcome = (tx.get("outcome") or "").lower()
            tx_name = (tx.get("treatment") or "").lower()
            if "fail" in outcome or "ineffective" in outcome or "intolerant" in outcome:
                for req in required_therapies:
                    if req in tx_name and req not in matched:
                        matched.append(req)

        is_met = len(matched) >= min_failures

        return RuleResult(
            criterion_code=code, description=desc, is_met=is_met,
            evidence=f"Failed therapies: {matched} ({len(matched)}/{min_failures})",
            rule_trace=f"therapy_failure: required={required_therapies}, min={min_failures}, found={matched}",
            confidence=1.0 if matched else 0.5, is_mandatory=mandatory,
        )

    def _eval_age_range(
        self, code: str, desc: str, params: dict, ctx: dict, mandatory: bool
    ) -> RuleResult:
        """Check if patient age is within required range."""
        min_age = params.get("min_age", 0)
        max_age = params.get("max_age", 150)

        dob = ctx["patient"].get("date_of_birth")
        if not dob:
            return RuleResult(
                criterion_code=code, description=desc, is_met=False,
                evidence="Patient DOB not available",
                rule_trace="age_range: DOB missing", confidence=0.0, is_mandatory=mandatory,
            )

        if isinstance(dob, str):
            dob = datetime.fromisoformat(dob.replace("Z", "+00:00"))
        age = (datetime.now() - dob).days // 365

        is_met = min_age <= age <= max_age

        return RuleResult(
            criterion_code=code, description=desc, is_met=is_met,
            evidence=f"Patient age: {age} (range: {min_age}-{max_age})",
            rule_trace=f"age_range: age={age}, min={min_age}, max={max_age}",
            confidence=1.0, is_mandatory=mandatory,
        )

    def _eval_diagnosis_present(
        self, code: str, desc: str, params: dict, ctx: dict, mandatory: bool
    ) -> RuleResult:
        """Check if specific diagnosis keywords are present in evidence."""
        keywords = [k.lower() for k in params.get("keywords", [])]
        match_type = params.get("match", "any")

        diagnosis = (ctx["evidence"].get("diagnosis_summary") or "").lower()
        justification = (ctx["evidence"].get("medical_necessity_justification") or "").lower()
        combined = f"{diagnosis} {justification}"

        matched = [k for k in keywords if k in combined]
        is_met = (len(matched) == len(keywords)) if match_type == "all" else (len(matched) > 0)

        return RuleResult(
            criterion_code=code, description=desc, is_met=is_met,
            evidence=f"Keywords found: {matched}" if matched else "No matching keywords",
            rule_trace=f"diagnosis_present({match_type}): keywords={keywords}, matched={matched}",
            confidence=0.9 if is_met else 0.7, is_mandatory=mandatory,
        )

    def _eval_imaging_required(
        self, code: str, desc: str, params: dict, ctx: dict, mandatory: bool
    ) -> RuleResult:
        """Check if required imaging studies are present."""
        required_types = [t.lower() for t in params.get("imaging_types", [])]

        imaging = ctx["evidence"].get("relevant_imaging") or []
        found = []
        for img in imaging:
            study = (img.get("study") or img.get("type") or "").lower()
            for req in required_types:
                if req in study:
                    found.append(req)

        is_met = len(found) > 0

        return RuleResult(
            criterion_code=code, description=desc, is_met=is_met,
            evidence=f"Found imaging: {found}" if found else f"Required imaging not found: {required_types}",
            rule_trace=f"imaging_required: required={required_types}, found={found}",
            confidence=1.0 if found else 0.5, is_mandatory=mandatory,
        )

    def _eval_time_constraint(
        self, code: str, desc: str, params: dict, ctx: dict, mandatory: bool
    ) -> RuleResult:
        """Check if treatment/imaging was done within a time window."""
        item_type = params.get("item_type", "treatment")  # treatment, imaging, lab
        max_days = params.get("max_days_ago", 365)
        keyword = params.get("keyword", "").lower()

        items = []
        if item_type == "treatment":
            items = ctx["evidence"].get("treatment_history") or []
        elif item_type == "imaging":
            items = ctx["evidence"].get("relevant_imaging") or []
        elif item_type == "lab":
            items = ctx["evidence"].get("relevant_lab_results") or []

        cutoff = datetime.now() - timedelta(days=max_days)
        found_in_window = False

        for item in items:
            name = (item.get("treatment") or item.get("study") or item.get("test") or "").lower()
            if keyword and keyword not in name:
                continue
            date_str = item.get("date", "")
            if date_str:
                try:
                    item_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if item_date >= cutoff:
                        found_in_window = True
                        break
                except (ValueError, TypeError):
                    found_in_window = True  # Can't parse date, assume valid
                    break

        return RuleResult(
            criterion_code=code, description=desc, is_met=found_in_window,
            evidence=f"{item_type} '{keyword}' within {max_days} days: {'found' if found_in_window else 'not found'}",
            rule_trace=f"time_constraint: {item_type}, keyword={keyword}, max_days={max_days}",
            confidence=0.9 if found_in_window else 0.5, is_mandatory=mandatory,
        )

    def _eval_composite(
        self, code: str, desc: str, params: dict, ctx: dict, mandatory: bool
    ) -> RuleResult:
        """Evaluate a composite rule (AND/OR of sub-rules)."""
        operator = params.get("operator", "and")  # "and" or "or"
        sub_rules = params.get("rules", [])

        sub_results = []
        for sub in sub_rules:
            sub_type = sub.get("type", "")
            sub_params = sub.get("params", {})
            evaluator = self._evaluators.get(sub_type)
            if evaluator:
                result = evaluator(
                    f"{code}.{sub_type}", sub.get("description", ""), sub_params, ctx, False
                )
                sub_results.append(result)

        if operator == "and":
            is_met = all(r.is_met for r in sub_results) if sub_results else False
        else:
            is_met = any(r.is_met for r in sub_results) if sub_results else False

        trace_parts = [f"{r.criterion_code}={'MET' if r.is_met else 'NOT MET'}" for r in sub_results]

        return RuleResult(
            criterion_code=code, description=desc, is_met=is_met,
            evidence=f"Composite({operator}): {', '.join(trace_parts)}",
            rule_trace=f"composite({operator}): {' {operator} '.join(trace_parts)}",
            confidence=sum(r.confidence for r in sub_results) / max(len(sub_results), 1),
            is_mandatory=mandatory,
        )


# Module-level singleton
rules_engine = RulesEngine()
