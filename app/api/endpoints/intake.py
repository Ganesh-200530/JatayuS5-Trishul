from __future__ import annotations

"""Public intake endpoints — no auth required.

Patients use a unique token link to upload medical documents and details.
A PA request is created with status 'intake_received' (AI evaluation NOT auto-started).
"""

import uuid
import os
import base64
import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from sqlalchemy import select

from app.database import SessionLocal
from app.models.intake_link import PatientIntakeLink, IntakeLinkStatus
from app.models.patient import Patient
from app.models.prior_auth import PriorAuthRequest, PAStatus, Urgency
from app.core.exceptions import AppError
from app.config import get_settings
from app.services.notifications import notify_documents_received

bp = Blueprint('intake', __name__)

_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _save_file(raw: bytes, filename: str) -> str:
    """Save uploaded file to disk and return the file_id (UUID-based)."""
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(filename)[1].lower() if filename else ''
    safe_name = file_id + ext
    path = os.path.join(UPLOAD_DIR, safe_name)
    with open(path, 'wb') as fh:
        fh.write(raw)
    return file_id + ext


def _parse_doc_json(raw: str) -> dict:
    """Best-effort parse of Gemini response as JSON."""
    text = raw.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {'extracted_text': raw, 'is_medical': True}


def _ocr_document(raw: bytes, mime: str, filename: str, file_id: str, settings, source: str = '') -> dict:
    """Run Gemini OCR on a document. Returns dict with keys:
    ok, doc_text, doc_record, warning.
    """
    fallback_record = {
        'filename': filename,
        'document_type': 'unknown',
        'summary': '',
        'extracted_text': f'[Document: {filename}]',
        'file_id': file_id,
    }
    if source:
        fallback_record['source'] = source

    if not settings.GEMINI_API_KEY:
        return {'ok': True, 'doc_text': f'[Document: {filename}]', 'doc_record': fallback_record, 'warning': None}

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        b64 = base64.b64encode(raw).decode()
        resp = model.generate_content([
            {'mime_type': mime, 'data': b64},
            (
                'Analyze this document. First, determine if it is a medical/healthcare document. '
                'Detect the language of the document. Extract all text in the original language. '
                'If the document is NOT in English, also provide an English translation of the extracted text. '
                'Respond with ONLY valid JSON (no markdown fences):\n'
                '{"is_medical": true/false, "extracted_text": "full text in original language", '
                '"language": "detected language (e.g. English, Spanish, Hindi, Arabic)", '
                '"english_translation": "English translation if non-English, otherwise null", '
                '"document_type": "medical_record|lab_report|prescription|non_medical|...", '
                '"brief_summary": "one sentence summary in English"}'
            ),
        ])
        raw_text = resp.text.strip() if resp.text else ''
        parsed = _parse_doc_json(raw_text)
        is_med = parsed.get('is_medical', True)
        extracted = parsed.get('extracted_text', raw_text)
        doc_type = parsed.get('document_type', 'unknown')
        summary = parsed.get('brief_summary', '')
        detected_lang = parsed.get('language', 'English')
        english_translation = parsed.get('english_translation')

        # Use translated text for pipeline if available
        pipeline_text = english_translation or extracted

        if not is_med or doc_type == 'non_medical':
            warning = (
                f"{filename} does not appear to be a medical document"
                + (f" ({summary})" if summary else "") + "."
            )
            return {'ok': False, 'doc_text': None, 'doc_record': None, 'warning': warning}

        record = {
            'filename': filename,
            'document_type': doc_type,
            'summary': summary,
            'extracted_text': extracted,
            'language': detected_lang,
            'file_id': file_id,
        }
        if english_translation:
            record['english_translation'] = english_translation
        if source:
            record['source'] = source

        return {'ok': True, 'doc_text': pipeline_text, 'doc_record': record, 'warning': None}
    except Exception:
        return {'ok': True, 'doc_text': f'[Document: {filename}]', 'doc_record': fallback_record, 'warning': None}


def _get_valid_link(db, token: str) -> PatientIntakeLink:
    """Validate token and return the intake link or raise."""
    link = db.execute(
        select(PatientIntakeLink).where(PatientIntakeLink.token == token)
    ).scalar_one_or_none()

    if not link:
        raise AppError("Invalid or expired intake link.", 404)

    if link.status == IntakeLinkStatus.USED:
        raise AppError("This intake link has already been used.", 410)

    now = datetime.utcnow()
    expires = link.expires_at.replace(tzinfo=None) if link.expires_at.tzinfo else link.expires_at

    if link.status == IntakeLinkStatus.EXPIRED or expires < now:
        # Mark as expired if not already
        if link.status != IntakeLinkStatus.EXPIRED:
            link.status = IntakeLinkStatus.EXPIRED
            db.commit()
        raise AppError("This intake link has expired.", 410)

    return link


@bp.route('/<token>/validate', methods=['GET'])
def validate_token(token: str):
    """Public: validate an intake token and return patient basic info."""
    db = SessionLocal()
    try:
        link = _get_valid_link(db, token)
        patient = db.execute(
            select(Patient).where(Patient.id == link.patient_id)
        ).scalar_one_or_none()

        if not patient:
            raise AppError("Patient not found.", 404)

        result = {
            "valid": True,
            "patient_name": f"{patient.first_name} {patient.last_name}",
            "patient_mrn": patient.mrn,
            "payer_name": patient.payer_name or patient.payer_id,
            "expires_at": link.expires_at.isoformat(),
        }

        # If this link is for additional documents on an existing PA
        if link.prior_auth_id:
            result["prior_auth_id"] = link.prior_auth_id
            result["missing_documents"] = link.missing_documents or []
            result["is_additional"] = True
        else:
            result["is_additional"] = False

        return jsonify(result)
    finally:
        db.close()


@bp.route('/<token>/submit', methods=['POST'])
def submit_intake(token: str):
    """Public: patient submits medical docs and details via intake link.

    Accepts multipart form with:
      - documents (files): medical document uploads
    All other fields (cpt_code, provider, urgency) are optional — filled by admin later.
    """
    db = SessionLocal()
    try:
        link = _get_valid_link(db, token)
        patient = db.execute(
            select(Patient).where(Patient.id == link.patient_id)
        ).scalar_one_or_none()

        if not patient:
            raise AppError("Patient not found.", 404)

        # Parse form data
        clinical_notes = request.form.get('clinical_notes', '')
        cpt_code = request.form.get('cpt_code', '')
        cpt_description = request.form.get('cpt_description', '')
        icd10_raw = request.form.get('icd10_codes', '')
        provider_name = request.form.get('provider_name', '')
        provider_npi = request.form.get('provider_npi', '')
        urgency_str = request.form.get('urgency', 'standard')

        # All fields are optional for patient intake — admin fills details later

        icd10_codes = [c.strip() for c in icd10_raw.split(',') if c.strip()] if icd10_raw else []

        urgency_map = {'standard': Urgency.STANDARD, 'urgent': Urgency.URGENT, 'emergent': Urgency.EMERGENT}
        urgency = urgency_map.get(urgency_str.lower(), Urgency.STANDARD)

        # Process uploaded documents — extract text via Gemini if available
        doc_texts = []
        doc_records = []  # structured per-document info
        doc_warnings = []
        uploaded_docs = request.files.getlist('documents')
        settings = get_settings()

        for f in uploaded_docs:
            if f.content_length and f.content_length > _MAX_SIZE:
                doc_warnings.append(f"Skipped {f.filename}: file too large (max 10 MB).")
                continue
            raw = f.read()
            if len(raw) > _MAX_SIZE:
                doc_warnings.append(f"Skipped {f.filename}: file too large (max 10 MB).")
                continue
            mime = f.content_type or 'application/octet-stream'

            # Save the original file to disk
            file_id = _save_file(raw, f.filename)

            # OCR via Gemini with multi-language support
            ocr = _ocr_document(raw, mime, f.filename, file_id, settings)
            if ocr['warning']:
                doc_warnings.append(ocr['warning'])
            if ocr['ok'] and ocr['doc_text']:
                doc_texts.append(ocr['doc_text'])
                doc_records.append(ocr['doc_record'])

        # Combine clinical notes with extracted document text (for pipeline)
        full_notes = clinical_notes
        if doc_texts:
            full_notes += "\n\n--- Uploaded Documents ---\n" + "\n\n".join(doc_texts)

        # Create PA request with intake_received status (NO auto AI)
        pa = PriorAuthRequest(
            patient_id=patient.id,
            cpt_code=cpt_code or 'PENDING',
            cpt_description=cpt_description or None,
            icd10_codes=icd10_codes,
            ordering_provider_npi=provider_npi or 'PENDING',
            ordering_provider_name=provider_name or None,
            payer_id=patient.payer_id,
            payer_name=patient.payer_name,
            urgency=urgency,
            status=PAStatus.INTAKE_RECEIVED,
            metadata_={"source": "patient_intake", "clinical_notes": full_notes, "intake_token": token, "documents": doc_records},
        )
        db.add(pa)

        # Mark the link as used
        link.status = IntakeLinkStatus.USED
        db.commit()
        db.refresh(pa)

        # Notify patient that documents were received
        if patient.email:
            notify_documents_received(patient.email, f"{patient.first_name} {patient.last_name}", len(doc_records))

        return jsonify({
            "success": True,
            "message": "Your documents have been submitted successfully. Your healthcare provider will review them.",
            "reference_id": pa.id,
            "warnings": doc_warnings if doc_warnings else None,
        }), 201
    finally:
        db.close()


@bp.route('/<token>/upload-additional', methods=['POST'])
def upload_additional_documents(token: str):
    """Public: patient uploads additional documents for an existing PA request.

    Used when the system requests missing documentation.
    Appends new document text to the existing PA's metadata and resets status.
    """
    db = SessionLocal()
    try:
        link = _get_valid_link(db, token)

        if not link.prior_auth_id:
            raise AppError("This link is not for additional document upload.", 400)

        patient = db.execute(
            select(Patient).where(Patient.id == link.patient_id)
        ).scalar_one_or_none()
        if not patient:
            raise AppError("Patient not found.", 404)

        pa = db.execute(
            select(PriorAuthRequest).where(PriorAuthRequest.id == link.prior_auth_id)
        ).scalar_one_or_none()
        if not pa:
            raise AppError("Prior authorization request not found.", 404)

        # Process uploaded documents
        doc_texts = []
        doc_records = []
        doc_warnings = []
        uploaded_docs = request.files.getlist('documents')
        settings = get_settings()

        for f in uploaded_docs:
            if f.content_length and f.content_length > _MAX_SIZE:
                doc_warnings.append(f"Skipped {f.filename}: file too large (max 10 MB).")
                continue
            raw = f.read()
            if len(raw) > _MAX_SIZE:
                doc_warnings.append(f"Skipped {f.filename}: file too large (max 10 MB).")
                continue
            mime = f.content_type or 'application/octet-stream'

            # Save the original file to disk
            file_id = _save_file(raw, f.filename)

            # OCR via Gemini with multi-language support
            ocr = _ocr_document(raw, mime, f.filename, file_id, settings, source='additional_request')
            if ocr['warning']:
                doc_warnings.append(ocr['warning'])
            if ocr['ok'] and ocr['doc_text']:
                doc_texts.append(ocr['doc_text'])
                doc_records.append(ocr['doc_record'])

        if not doc_texts:
            raise AppError("No valid medical documents were uploaded.", 400)

        # Append new document text to existing PA metadata
        meta = dict(pa.metadata_) if pa.metadata_ else {}
        existing_notes = meta.get('clinical_notes', '')

        additional_section = "\n\n--- Additional Documents (Requested) ---\n" + "\n\n".join(doc_texts)
        meta['clinical_notes'] = existing_notes + additional_section
        existing_docs = meta.get('documents', [])
        if not isinstance(existing_docs, list):
            existing_docs = []
        meta['documents'] = existing_docs + doc_records
        meta['additional_docs_received'] = True
        meta['additional_docs_received_at'] = datetime.now(timezone.utc).isoformat()
        meta['documents_requested'] = False
        pa.metadata_ = meta

        # Reset PA status so admin can re-evaluate
        pa.status = PAStatus.INTAKE_RECEIVED
        pa.requires_human_review = False
        pa.human_review_reason = None

        # Mark the link as used
        link.status = IntakeLinkStatus.USED
        db.commit()

        return jsonify({
            "success": True,
            "message": "Your additional documents have been submitted successfully. Your healthcare provider will review them.",
            "reference_id": pa.id,
            "warnings": doc_warnings if doc_warnings else None,
        }), 201
    finally:
        db.close()
