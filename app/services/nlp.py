from __future__ import annotations

"""Medical NLP preprocessing — NER, negation detection, section parsing, abbreviation expansion."""

import re
import structlog
from typing import NamedTuple

logger = structlog.get_logger()

_nlp = None
_nlp_available = False

# ── Medical abbreviation dictionary ─────────────────────────

MEDICAL_ABBREVIATIONS: dict[str, str] = {
    "htn": "hypertension",
    "dm": "diabetes mellitus",
    "dm2": "type 2 diabetes mellitus",
    "t2dm": "type 2 diabetes mellitus",
    "chf": "congestive heart failure",
    "copd": "chronic obstructive pulmonary disease",
    "cad": "coronary artery disease",
    "ckd": "chronic kidney disease",
    "afib": "atrial fibrillation",
    "a-fib": "atrial fibrillation",
    "mi": "myocardial infarction",
    "cva": "cerebrovascular accident",
    "tia": "transient ischemic attack",
    "dvt": "deep vein thrombosis",
    "pe": "pulmonary embolism",
    "uti": "urinary tract infection",
    "uri": "upper respiratory infection",
    "sob": "shortness of breath",
    "cp": "chest pain",
    "abd": "abdominal",
    "hx": "history",
    "fx": "fracture",
    "tx": "treatment",
    "dx": "diagnosis",
    "rx": "prescription",
    "sx": "symptoms",
    "prn": "as needed",
    "bid": "twice daily",
    "tid": "three times daily",
    "qid": "four times daily",
    "qd": "once daily",
    "qhs": "at bedtime",
    "ac": "before meals",
    "pc": "after meals",
    "po": "by mouth",
    "iv": "intravenous",
    "im": "intramuscular",
    "sq": "subcutaneous",
    "r/o": "rule out",
    "w/u": "workup",
    "f/u": "follow up",
    "s/p": "status post",
    "c/o": "complains of",
    "nka": "no known allergies",
    "nkda": "no known drug allergies",
    "bmp": "basic metabolic panel",
    "cbc": "complete blood count",
    "cmp": "comprehensive metabolic panel",
    "lfts": "liver function tests",
    "ua": "urinalysis",
    "ekg": "electrocardiogram",
    "ecg": "electrocardiogram",
    "ct": "computed tomography",
    "mri": "magnetic resonance imaging",
    "npo": "nothing by mouth",
    "wbc": "white blood cell count",
    "rbc": "red blood cell count",
    "hgb": "hemoglobin",
    "hct": "hematocrit",
    "plt": "platelet count",
    "bun": "blood urea nitrogen",
    "cr": "creatinine",
    "gfr": "glomerular filtration rate",
    "a1c": "hemoglobin a1c",
    "hba1c": "hemoglobin a1c",
    "bp": "blood pressure",
    "hr": "heart rate",
    "rr": "respiratory rate",
    "spo2": "oxygen saturation",
    "bmi": "body mass index",
    "pt": "physical therapy",
    "ot": "occupational therapy",
    "nsaids": "nonsteroidal anti-inflammatory drugs",
    "asa": "aspirin",
    "abx": "antibiotics",
    "oa": "osteoarthritis",
    "ra": "rheumatoid arthritis",
    "sle": "systemic lupus erythematosus",
    "ms": "multiple sclerosis",
    "als": "amyotrophic lateral sclerosis",
    "gerd": "gastroesophageal reflux disease",
    "ibs": "irritable bowel syndrome",
    "osa": "obstructive sleep apnea",
}

# ── Negation patterns ──────────────────────────────────────

NEGATION_TRIGGERS = [
    "no ", "not ", "without ", "denies ", "denied ", "negative for ",
    "no evidence of ", "no signs of ", "no history of ", "absent ",
    "rules out ", "ruled out ", "never ", "none ", "unremarkable ",
    "no significant ", "no acute ", "does not have ",
]

# ── Clinical section headers ───────────────────────────────

SECTION_PATTERNS = {
    "chief_complaint": r"(?i)(chief complaint|cc|reason for visit|presenting complaint)[:\s]",
    "hpi": r"(?i)(history of present illness|hpi|present illness)[:\s]",
    "past_medical_history": r"(?i)(past medical history|pmh|medical history|pmhx)[:\s]",
    "medications": r"(?i)(medications|current medications|med list|medication list|home medications)[:\s]",
    "allergies": r"(?i)(allergies|drug allergies|medication allergies)[:\s]",
    "family_history": r"(?i)(family history|fhx|family hx)[:\s]",
    "social_history": r"(?i)(social history|shx|social hx)[:\s]",
    "review_of_systems": r"(?i)(review of systems|ros)[:\s]",
    "physical_exam": r"(?i)(physical examination|physical exam|pe|exam|examination)[:\s]",
    "vitals": r"(?i)(vital signs|vitals)[:\s]",
    "labs": r"(?i)(laboratory|lab results|labs|laboratory results)[:\s]",
    "imaging": r"(?i)(imaging|radiology|imaging results|x-ray|ct scan|mri)[:\s]",
    "assessment": r"(?i)(assessment|impression|clinical impression)[:\s]",
    "plan": r"(?i)(plan|treatment plan|management plan)[:\s]",
    "assessment_and_plan": r"(?i)(assessment and plan|assessment & plan|a&p|a/p)[:\s]",
}


class NLPEntity(NamedTuple):
    text: str
    label: str  # CONDITION, MEDICATION, PROCEDURE, LAB_TEST, ANATOMY, etc.
    start: int
    end: int
    negated: bool
    section: str | None


class ClinicalSection(NamedTuple):
    name: str
    text: str
    start: int
    end: int


def _load_spacy():
    global _nlp, _nlp_available
    if _nlp is not None:
        return _nlp if _nlp_available else None
    try:
        import spacy
        from app.config import get_settings
        _nlp = spacy.load(get_settings().SPACY_MODEL)
        _nlp_available = True
        logger.info("nlp.spacy_loaded", model=get_settings().SPACY_MODEL)
        return _nlp
    except Exception as exc:
        _nlp_available = False
        logger.warning("nlp.spacy_unavailable_using_regex", error=str(exc))
        return None


def expand_abbreviations(text: str) -> str:
    """Expand common medical abbreviations in clinical text."""
    result = text
    for abbr, expansion in MEDICAL_ABBREVIATIONS.items():
        # Match word boundaries to avoid partial replacements
        pattern = r"\b" + re.escape(abbr) + r"\b"
        result = re.sub(pattern, f"{expansion} ({abbr})", result, flags=re.IGNORECASE)
    return result


def detect_negation(text: str, entity_start: int, window: int = 60) -> bool:
    """Check if a clinical entity is negated based on surrounding context."""
    # Look in a window before the entity
    start = max(0, entity_start - window)
    context = text[start:entity_start].lower()
    return any(trigger in context for trigger in NEGATION_TRIGGERS)


def parse_sections(text: str) -> list[ClinicalSection]:
    """Segment clinical notes into standard sections (HPI, PMH, Meds, etc.)."""
    sections: list[ClinicalSection] = []
    matches = []

    for section_name, pattern in SECTION_PATTERNS.items():
        for m in re.finditer(pattern, text):
            matches.append((m.start(), section_name, m.end()))

    # Sort by position in text
    matches.sort(key=lambda x: x[0])

    for i, (start, name, content_start) in enumerate(matches):
        end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        section_text = text[content_start:end].strip()
        sections.append(ClinicalSection(name=name, text=section_text, start=start, end=end))

    # If no sections found, treat entire text as one section
    if not sections:
        sections.append(ClinicalSection(name="full_note", text=text, start=0, end=len(text)))

    return sections


def extract_entities(text: str) -> list[NLPEntity]:
    """Extract medical entities using spaCy NER (with regex fallback)."""
    nlp = _load_spacy()
    sections = parse_sections(text)
    entities: list[NLPEntity] = []

    def _get_section(pos: int) -> str | None:
        for sec in sections:
            if sec.start <= pos < sec.end:
                return sec.name
        return None

    if nlp:
        doc = nlp(text)
        for ent in doc.ents:
            # Map spaCy entity labels to clinical categories
            label_map = {
                "PERSON": "PERSON",
                "ORG": "ORGANIZATION",
                "DATE": "DATE",
                "CARDINAL": "VALUE",
                "QUANTITY": "VALUE",
            }
            label = label_map.get(ent.label_, "CLINICAL")
            negated = detect_negation(text, ent.start_char)
            section = _get_section(ent.start_char)
            entities.append(NLPEntity(
                text=ent.text, label=label, start=ent.start_char, end=ent.end_char,
                negated=negated, section=section,
            ))

    # Regex-based medical entity extraction (always runs as supplement)
    medication_pattern = r"\b(metformin|lisinopril|amlodipine|atorvastatin|omeprazole|metoprolol|losartan|gabapentin|hydrochlorothiazide|levothyroxine|prednisone|ibuprofen|acetaminophen|aspirin|warfarin|heparin|insulin|albuterol|fluticasone|montelukast|amoxicillin|azithromycin|ciprofloxacin|doxycycline|cephalexin)\b"
    for m in re.finditer(medication_pattern, text, re.IGNORECASE):
        negated = detect_negation(text, m.start())
        section = _get_section(m.start())
        entities.append(NLPEntity(
            text=m.group(), label="MEDICATION", start=m.start(), end=m.end(),
            negated=negated, section=section,
        ))

    # ICD-10 code pattern
    icd_pattern = r"\b([A-Z]\d{2}(?:\.\d{1,4})?)\b"
    for m in re.finditer(icd_pattern, text):
        entities.append(NLPEntity(
            text=m.group(), label="ICD10_CODE", start=m.start(), end=m.end(),
            negated=False, section=_get_section(m.start()),
        ))

    # CPT code pattern
    cpt_pattern = r"\b(\d{5})\b"
    for m in re.finditer(cpt_pattern, text):
        entities.append(NLPEntity(
            text=m.group(), label="CPT_CODE", start=m.start(), end=m.end(),
            negated=False, section=_get_section(m.start()),
        ))

    # Lab value pattern (e.g., "HbA1c 7.2%", "WBC 12.3")
    lab_pattern = r"\b(hba1c|a1c|wbc|rbc|hgb|hct|plt|bun|creatinine|gfr|glucose|sodium|potassium|calcium|tsh|inr|ptt|ast|alt|ldl|hdl|triglycerides)\s*[=:>]?\s*(\d+\.?\d*)\s*(%|mg/dl|g/dl|mmol/l|u/l|ml/min|k/ul|cells/ul)?"
    for m in re.finditer(lab_pattern, text, re.IGNORECASE):
        entities.append(NLPEntity(
            text=m.group(), label="LAB_RESULT", start=m.start(), end=m.end(),
            negated=detect_negation(text, m.start()), section=_get_section(m.start()),
        ))

    return entities


def preprocess_clinical_text(text: str) -> dict:
    """
    Full NLP preprocessing pipeline:
    1. Expand abbreviations
    2. Parse sections
    3. Extract entities
    4. Detect negations
    5. Return structured result
    """
    if not text or not text.strip():
        return {
            "expanded_text": "",
            "sections": [],
            "entities": [],
            "negated_entities": [],
            "medications": [],
            "conditions": [],
            "lab_results": [],
            "icd_codes": [],
        }

    expanded = expand_abbreviations(text)
    sections = parse_sections(expanded)
    entities = extract_entities(expanded)

    negated = [e for e in entities if e.negated]
    affirmed = [e for e in entities if not e.negated]

    medications = [e for e in affirmed if e.label == "MEDICATION"]
    lab_results = [e for e in affirmed if e.label == "LAB_RESULT"]
    icd_codes = [e for e in entities if e.label == "ICD10_CODE"]
    conditions = [e for e in affirmed if e.label == "CLINICAL"]

    return {
        "expanded_text": expanded,
        "sections": [{"name": s.name, "text": s.text[:500]} for s in sections],
        "entities": [
            {"text": e.text, "label": e.label, "negated": e.negated, "section": e.section}
            for e in entities
        ],
        "negated_entities": [
            {"text": e.text, "label": e.label, "section": e.section}
            for e in negated
        ],
        "medications": [{"name": e.text, "negated": e.negated, "section": e.section} for e in medications],
        "conditions": [{"text": e.text, "section": e.section} for e in conditions],
        "lab_results": [{"text": e.text, "section": e.section} for e in lab_results],
        "icd_codes": [e.text for e in icd_codes],
    }


def is_spacy_available() -> bool:
    _load_spacy()
    return _nlp_available
