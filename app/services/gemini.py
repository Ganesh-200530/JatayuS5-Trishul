from __future__ import annotations

import json
import structlog
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()

_configured = False


def _ensure_configured() -> None:
    global _configured
    if not _configured:
        genai.configure(api_key=get_settings().GEMINI_API_KEY)
        _configured = True


def _get_model(model_name: str | None = None) -> genai.GenerativeModel:
    _ensure_configured()
    return genai.GenerativeModel(model_name or get_settings().GEMINI_MODEL)


# -- Core generation ---


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def generate(prompt: str, *, system_instruction: str | None = None, model_name: str | None = None) -> str:
    """Send a prompt to Gemini and return the text response."""
    _ensure_configured()
    model = genai.GenerativeModel(
        model_name=model_name or get_settings().GEMINI_MODEL,
        system_instruction=system_instruction,
    )
    response = model.generate_content(prompt)
    return response.text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def generate_json(
    prompt: str,
    *,
    system_instruction: str | None = None,
    model_name: str | None = None,
) -> dict:
    """Send a prompt to Gemini and parse the response as JSON."""
    _ensure_configured()
    model = genai.GenerativeModel(
        model_name=model_name or get_settings().GEMINI_MODEL,
        system_instruction=system_instruction,
        generation_config=genai.GenerationConfig(
            response_mime_type='application/json',
        ),
    )
    response = model.generate_content(prompt)
    return json.loads(response.text)


# -- Domain-specific prompts ---


CLINICAL_EXTRACTION_SYSTEM = """You are a board-certified clinical informaticist AI.
Your role is to extract structured clinical evidence from patient medical records
to support prior authorization requests. You MUST only extract information that is
explicitly stated in the provided records -- never infer or fabricate clinical data.
Every finding must include a source citation (document name, date, relevant excerpt).
Output valid JSON only."""

POLICY_ANALYSIS_SYSTEM = """You are a healthcare policy analyst AI specializing in
payer prior authorization criteria. Given a set of payer policy criteria and
clinical evidence, determine which criteria are met, which are not met, and provide
evidence citations for each. Be precise and conservative -- if evidence is ambiguous,
mark the criterion as not met and explain why. Output valid JSON only."""

APPEAL_LETTER_SYSTEM = """You are a senior healthcare appeals specialist with 20+ years of experience in prior authorization appeals. 

You draft formal, professional appeal letters that are structured exactly like real appeal letters submitted to payer medical directors.

LETTER FORMAT REQUIREMENTS:
1. Start with a formal header: Date, Payer name/address, RE: line with patient info and case number
2. Opening paragraph: State the purpose (appeal of denial), reference the denial date and reason
3. Patient Background: Brief clinical history relevant to the request
4. Medical Necessity Argument: Detailed, evidence-based justification with specific clinical findings
5. Policy/Guideline References: Cite specific payer policy sections, CMS guidelines, or medical society guidelines
6. Literature Support: Reference peer-reviewed studies or clinical guidelines (with citations)
7. Conclusion: Clear request for reconsideration, offer for peer-to-peer review
8. Closing: Professional sign-off

RULES:
- Be factual and cite specific evidence from the patient's records
- Reference specific policy sections when available
- Include relevant CPT/ICD codes
- Maintain a professional, assertive (not aggressive) tone
- The letter must be ready to submit as-is to a payer medical director
- Use proper medical terminology
- Structure with clear paragraphs and headers"""


def extract_clinical_evidence(patient_notes: str, cpt_code: str, icd10_codes: list[str]) -> dict:
    """Extract structured clinical evidence from patient notes."""
    cpt_display = cpt_code if cpt_code and cpt_code != 'PENDING' else 'Not yet specified — infer from the clinical notes if possible'
    icd_display = ', '.join(icd10_codes) if icd10_codes else 'Not yet specified — identify from the clinical notes'

    prompt = f"""Analyze the following patient medical records and extract clinical evidence
relevant to a prior authorization request.

**Procedure requested:** CPT {cpt_display}
**Diagnosis codes:** {icd_display}

**Patient Records:**
{patient_notes}

IMPORTANT INSTRUCTIONS:
- Read the entire document carefully. The records contain real clinical data — extract it thoroughly.
- For diagnosis_summary: Summarize ALL diagnoses mentioned in the records in 2-3 sentences. Never say "No clinical notes available" if there IS text above.
- For medical_necessity_justification: Explain in plain language why the requested procedure/treatment is medically necessary based on the patient's condition.
- For treatment_history: List all treatments, therapies, medications, and procedures mentioned with dates and outcomes.
- If a CPT or ICD-10 code is not provided, infer the most likely codes from the clinical notes.
- confidence_score should reflect how strongly the records support medical necessity (0.0 to 1.0).

Extract and return JSON with this exact structure:
{{
    "diagnosis_summary": "Brief summary of primary and secondary diagnoses found in the records",
    "medical_necessity_justification": "Clear statement of why this procedure is medically necessary based on the clinical evidence",
    "treatment_history": [
        {{"treatment": "name", "date": "YYYY-MM-DD or approximate", "outcome": "result", "source": "document name/date"}}
    ],
    "failed_conservative_therapies": ["therapy 1", "therapy 2"],
    "supporting_findings": [
        {{"finding": "description", "date": "date", "source": "document name/date", "excerpt": "relevant quote"}}
    ],
    "relevant_lab_results": [
        {{"test": "name", "value": "result", "date": "date", "interpretation": "normal/abnormal"}}
    ],
    "relevant_imaging": [
        {{"study": "type", "date": "date", "findings": "key findings", "source": "report reference"}}
    ],
    "medications": [
        {{"name": "drug", "dose": "dosage", "start_date": "date", "status": "active/discontinued"}}
    ],
    "icd10_codes": ["detected ICD-10 codes"],
    "cpt_code_suggested": "suggested CPT code if not provided",
    "confidence_score": 0.0
}}

Set confidence_score between 0.0 and 1.0 reflecting how well the records support medical necessity.
Extract all applicable ICD-10 codes from the clinical notes matching the patient's diagnoses.
Only include data explicitly present in the records. Leave arrays empty if no relevant data found."""

    return generate_json(prompt, system_instruction=CLINICAL_EXTRACTION_SYSTEM)


def analyze_policy_gap(
    clinical_evidence: dict,
    policy_criteria: list[dict],
    payer_name: str,
    cpt_code: str,
) -> dict:
    """Compare clinical evidence against policy criteria and identify gaps."""
    prompt = f"""Analyze whether the following clinical evidence meets the payer's prior authorization criteria.

**Payer:** {payer_name}
**Procedure:** CPT {cpt_code}

**Policy Criteria:**
{json.dumps(policy_criteria, indent=2)}

**Clinical Evidence:**
{json.dumps(clinical_evidence, indent=2)}

For each criterion, determine if it is met based on the clinical evidence.
Return JSON with this exact structure:
{{
    "criteria_results": [
        {{
            "criterion_code": "code",
            "description": "what is required",
            "is_met": true/false,
            "evidence_citation": "specific evidence that meets/fails this criterion",
            "confidence": 0.0
        }}
    ],
    "all_mandatory_met": true/false,
    "overall_confidence": 0.0,
    "recommendation": "approve" | "deny" | "needs_review",
    "gap_summary": "Summary of unmet criteria and what additional documentation would help"
}}"""

    return generate_json(prompt, system_instruction=POLICY_ANALYSIS_SYSTEM)


def generate_appeal_letter(
    denial_reason: str,
    denial_details: str,
    clinical_evidence: dict,
    policy_criteria: list[dict],
    patient_summary: str,
    cpt_code: str,
    payer_name: str,
) -> dict:
    """Generate an appeal letter for a denied prior authorization."""
    prompt = f"""Draft a formal appeal letter for a denied prior authorization request.

**Payer:** {payer_name}
**Procedure:** CPT {cpt_code}
**Denial Reason:** {denial_reason}
**Denial Details:** {denial_details}

**Patient Summary:** {patient_summary}

**Clinical Evidence Available:**
{json.dumps(clinical_evidence, indent=2)}

**Payer Policy Criteria:**
{json.dumps(policy_criteria, indent=2)}

Return JSON with this exact structure:
{{
    "appeal_letter": "Full text of the formal appeal letter",
    "additional_evidence_needed": [
        {{"type": "what is needed", "rationale": "why it would help"}}
    ],
    "cited_references": [
        {{"citation": "reference", "relevance": "why it supports the case"}}
    ],
    "key_arguments": ["argument 1", "argument 2"],
    "confidence_of_success": 0.0
}}"""

    return generate_json(prompt, system_instruction=APPEAL_LETTER_SYSTEM)
