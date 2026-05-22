from __future__ import annotations

"""X12 278 Health Care Services Review — EDI transaction generation and parsing.

Generates X12 278 (prior authorization request) and parses 278 response transactions
for clearinghouse-based payer submission (Availity, Change Healthcare, etc.).
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()

# X12 delimiters
SEGMENT_TERMINATOR = "~"
ELEMENT_SEPARATOR = "*"
SUB_ELEMENT_SEPARATOR = ":"
REPETITION_SEPARATOR = "^"


class X12_278Generator:
    """Generate X12 278 (Health Care Services Review Request) transactions."""

    def __init__(self):
        self.control_number = 1

    def generate_request(
        self,
        pa_request: dict,
        patient: dict,
        evidence: dict | None = None,
        sender_id: str = "AUTOAUTH",
        receiver_id: str = "PAYER001",
    ) -> str:
        """
        Generate a complete X12 278 request transaction.

        Returns the EDI text ready for submission to a clearinghouse.
        """
        self.control_number += 1
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M")
        ctrl = str(self.control_number).zfill(9)

        segments = []

        # ISA — Interchange Control Header
        segments.append(self._isa_segment(sender_id, receiver_id, date_str, time_str, ctrl))

        # GS — Functional Group Header
        segments.append(self._gs_segment(sender_id, receiver_id, date_str, time_str, ctrl))

        # ST — Transaction Set Header
        segments.append(f"ST{ELEMENT_SEPARATOR}278{ELEMENT_SEPARATOR}{ctrl.zfill(4)}")

        # BHT — Beginning of Hierarchical Transaction
        segments.append(
            f"BHT{ELEMENT_SEPARATOR}0007{ELEMENT_SEPARATOR}13{ELEMENT_SEPARATOR}"
            f"{str(uuid.uuid4())[:20]}{ELEMENT_SEPARATOR}{date_str}{ELEMENT_SEPARATOR}{time_str}"
        )

        # ── Hierarchical Level 1: Utilization Management Organization (Payer) ──
        segments.append(f"HL{ELEMENT_SEPARATOR}1{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}20{ELEMENT_SEPARATOR}1")

        # NM1 — Payer Name
        payer_id = pa_request.get("payer_id", "UNKNOWN")
        payer_name = pa_request.get("payer_name", "UNKNOWN PAYER")
        segments.append(
            f"NM1{ELEMENT_SEPARATOR}X3{ELEMENT_SEPARATOR}2{ELEMENT_SEPARATOR}"
            f"{payer_name[:60]}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}"
            f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}PI{ELEMENT_SEPARATOR}{payer_id}"
        )

        # ── Hierarchical Level 2: Requester (Provider) ──
        segments.append(f"HL{ELEMENT_SEPARATOR}2{ELEMENT_SEPARATOR}1{ELEMENT_SEPARATOR}21{ELEMENT_SEPARATOR}1")

        # NM1 — Requesting Provider
        npi = pa_request.get("ordering_provider_npi", "")
        provider_name = pa_request.get("ordering_provider_name", "PROVIDER")
        name_parts = provider_name.split(" ", 1) if provider_name else ["PROVIDER", ""]
        last_name = name_parts[-1] if len(name_parts) > 1 else name_parts[0]
        first_name = name_parts[0] if len(name_parts) > 1 else ""

        segments.append(
            f"NM1{ELEMENT_SEPARATOR}SJ{ELEMENT_SEPARATOR}1{ELEMENT_SEPARATOR}"
            f"{last_name[:60]}{ELEMENT_SEPARATOR}{first_name[:35]}{ELEMENT_SEPARATOR}"
            f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}XX{ELEMENT_SEPARATOR}{npi}"
        )

        # REF — Provider Tax ID
        segments.append(f"REF{ELEMENT_SEPARATOR}EI{ELEMENT_SEPARATOR}{npi}")

        # ── Hierarchical Level 3: Subscriber (Patient) ──
        segments.append(f"HL{ELEMENT_SEPARATOR}3{ELEMENT_SEPARATOR}2{ELEMENT_SEPARATOR}22{ELEMENT_SEPARATOR}1")

        # DMG — Patient Demographics
        dob = patient.get("date_of_birth", "")
        if isinstance(dob, datetime):
            dob = dob.strftime("%Y%m%d")
        elif isinstance(dob, str) and "T" in dob:
            dob = dob[:10].replace("-", "")

        gender_map = {"male": "M", "female": "F", "other": "U"}
        gender = gender_map.get(patient.get("gender", "").lower(), "U")

        segments.append(f"DMG{ELEMENT_SEPARATOR}D8{ELEMENT_SEPARATOR}{dob}{ELEMENT_SEPARATOR}{gender}")

        # NM1 — Patient Name
        segments.append(
            f"NM1{ELEMENT_SEPARATOR}IL{ELEMENT_SEPARATOR}1{ELEMENT_SEPARATOR}"
            f"{patient.get('last_name', '')[:60]}{ELEMENT_SEPARATOR}"
            f"{patient.get('first_name', '')[:35]}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}"
            f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}MI{ELEMENT_SEPARATOR}"
            f"{patient.get('subscriber_id', patient.get('mrn', ''))}"
        )

        # ── Hierarchical Level 4: Service Review ──
        segments.append(f"HL{ELEMENT_SEPARATOR}4{ELEMENT_SEPARATOR}3{ELEMENT_SEPARATOR}EV{ELEMENT_SEPARATOR}0")

        # UM — Health Care Services Review Information
        urgency_map = {"standard": "S", "urgent": "U", "emergent": "E"}
        urgency = urgency_map.get(pa_request.get("urgency", "standard"), "S")
        segments.append(
            f"UM{ELEMENT_SEPARATOR}HS{ELEMENT_SEPARATOR}I{ELEMENT_SEPARATOR}"
            f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}"
            f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{urgency}"
        )

        # SV1 — Professional Service (CPT code)
        cpt = pa_request.get("cpt_code", "")
        cpt_desc = pa_request.get("cpt_description", "")
        segments.append(
            f"SV1{ELEMENT_SEPARATOR}HC{SUB_ELEMENT_SEPARATOR}{cpt}"
            f"{SUB_ELEMENT_SEPARATOR}{cpt_desc[:80] if cpt_desc else ''}"
            f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}UN{ELEMENT_SEPARATOR}1"
        )

        # DTP — Service Date
        segments.append(f"DTP{ELEMENT_SEPARATOR}472{ELEMENT_SEPARATOR}D8{ELEMENT_SEPARATOR}{date_str}")

        # HI — Diagnosis Codes
        icd10_codes = pa_request.get("icd10_codes", [])
        if icd10_codes:
            hi_elements = [f"ABK{SUB_ELEMENT_SEPARATOR}{icd10_codes[0].replace('.', '')}"]
            for icd in icd10_codes[1:5]:  # Max 4 additional
                hi_elements.append(f"ABF{SUB_ELEMENT_SEPARATOR}{icd.replace('.', '')}")
            segments.append(f"HI{ELEMENT_SEPARATOR}" + ELEMENT_SEPARATOR.join(hi_elements))

        # PWK — Paperwork (attachments indicator)
        if evidence:
            segments.append(
                f"PWK{ELEMENT_SEPARATOR}OZ{ELEMENT_SEPARATOR}EL{ELEMENT_SEPARATOR}"
                f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}AC{ELEMENT_SEPARATOR}"
                f"{str(pa_request.get('id', ''))[:30]}"
            )

        # SE — Transaction Set Trailer
        segment_count = len(segments) + 1  # Include SE itself
        segments.append(f"SE{ELEMENT_SEPARATOR}{segment_count}{ELEMENT_SEPARATOR}{ctrl.zfill(4)}")

        # GE — Functional Group Trailer
        segments.append(f"GE{ELEMENT_SEPARATOR}1{ELEMENT_SEPARATOR}{ctrl}")

        # IEA — Interchange Control Trailer
        segments.append(f"IEA{ELEMENT_SEPARATOR}1{ELEMENT_SEPARATOR}{ctrl}")

        return SEGMENT_TERMINATOR.join(segments) + SEGMENT_TERMINATOR

    def _isa_segment(self, sender: str, receiver: str, date: str, time: str, ctrl: str) -> str:
        return (
            f"ISA{ELEMENT_SEPARATOR}00{ELEMENT_SEPARATOR}          "
            f"{ELEMENT_SEPARATOR}00{ELEMENT_SEPARATOR}          "
            f"{ELEMENT_SEPARATOR}ZZ{ELEMENT_SEPARATOR}{sender:<15}"
            f"{ELEMENT_SEPARATOR}ZZ{ELEMENT_SEPARATOR}{receiver:<15}"
            f"{ELEMENT_SEPARATOR}{date[2:]}{ELEMENT_SEPARATOR}{time}"
            f"{ELEMENT_SEPARATOR}{REPETITION_SEPARATOR}"
            f"{ELEMENT_SEPARATOR}00501{ELEMENT_SEPARATOR}{ctrl}"
            f"{ELEMENT_SEPARATOR}0{ELEMENT_SEPARATOR}P"
            f"{ELEMENT_SEPARATOR}{SUB_ELEMENT_SEPARATOR}"
        )

    def _gs_segment(self, sender: str, receiver: str, date: str, time: str, ctrl: str) -> str:
        return (
            f"GS{ELEMENT_SEPARATOR}HI{ELEMENT_SEPARATOR}{sender}"
            f"{ELEMENT_SEPARATOR}{receiver}{ELEMENT_SEPARATOR}{date}"
            f"{ELEMENT_SEPARATOR}{time}{ELEMENT_SEPARATOR}{ctrl}"
            f"{ELEMENT_SEPARATOR}X{ELEMENT_SEPARATOR}005010X217"
        )


class X12_278Parser:
    """Parse X12 278 response transactions."""

    def parse_response(self, edi_text: str) -> dict:
        """Parse a 278 response and extract decision details."""
        segments = [s.strip() for s in edi_text.split(SEGMENT_TERMINATOR) if s.strip()]
        result = {
            "transaction_type": "278_response",
            "decision": None,
            "tracking_number": None,
            "reason_codes": [],
            "effective_date": None,
            "review_status": None,
            "provider_info": {},
            "patient_info": {},
            "service_info": {},
        }

        for segment in segments:
            elements = segment.split(ELEMENT_SEPARATOR)
            seg_id = elements[0] if elements else ""

            if seg_id == "HCR":
                # Health Care Services Review Decision
                if len(elements) > 1:
                    decision_map = {
                        "A1": "approved", "A2": "approved_modified",
                        "A3": "denied", "A4": "pended", "A6": "partial_approval",
                        "CT": "contact_payer",
                    }
                    result["decision"] = decision_map.get(elements[1], elements[1])
                if len(elements) > 2:
                    result["tracking_number"] = elements[2]
                if len(elements) > 3:
                    result["reason_codes"] = elements[3].split(SUB_ELEMENT_SEPARATOR)

            elif seg_id == "UM":
                if len(elements) > 1:
                    result["review_status"] = elements[1]

            elif seg_id == "NM1":
                if len(elements) > 2:
                    role = elements[1]
                    name = elements[3] if len(elements) > 3 else ""
                    if role == "IL":
                        result["patient_info"]["name"] = name
                    elif role in ("SJ", "71"):
                        result["provider_info"]["name"] = name

            elif seg_id == "DTP":
                if len(elements) > 2 and elements[1] == "472":
                    result["effective_date"] = elements[2] if len(elements) > 2 else None

            elif seg_id == "SV1":
                if len(elements) > 1:
                    sub = elements[1].split(SUB_ELEMENT_SEPARATOR)
                    result["service_info"]["cpt_code"] = sub[1] if len(sub) > 1 else ""

            elif seg_id == "AAA":
                # Request Validation
                if len(elements) > 3:
                    result["reason_codes"].append(elements[3])

        return result


# Module-level singletons
x12_generator = X12_278Generator()
x12_parser = X12_278Parser()
