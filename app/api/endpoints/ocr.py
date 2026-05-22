from __future__ import annotations

"""OCR endpoint -- extract text from uploaded images/PDFs using Gemini Vision."""

import base64
import json

from flask import Blueprint, request, jsonify
from app.core.security import get_current_user
from app.core.exceptions import AppError
from app.database import SessionLocal
from app.config import get_settings

bp = Blueprint('ocr', __name__)

_MAX_SIZE = 10 * 1024 * 1024  # 10 MB

_ALLOWED_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif',
    'image/bmp', 'image/tiff', 'application/pdf',
}

_DOC_TYPE_LABELS = {
    'medical_record': 'Medical Record',
    'lab_report': 'Lab Report',
    'prescription': 'Prescription',
    'insurance_form': 'Insurance Form',
    'referral_letter': 'Referral Letter',
    'radiology_report': 'Radiology Report',
    'surgical_note': 'Surgical Note',
    'non_medical': 'Non-Medical Document',
    'unknown': 'Unknown',
}


@bp.route('/validate', methods=['POST'])
def validate_document():
    """Quick validation: checks if an uploaded file is a valid medical document.

    No auth required so the patient intake page can use it too.
    Returns is_medical, document_type, confidence, and a user-friendly message.
    Also extracts patient name/DOB from the document for cross-verification.
    """
    if 'file' not in request.files:
        raise AppError('No file uploaded', 400)

    file = request.files['file']
    if not file.filename:
        raise AppError('Empty filename', 400)

    contents = file.read()
    if len(contents) == 0:
        raise AppError('Empty file', 400)
    if len(contents) > _MAX_SIZE:
        raise AppError('File too large. Max 10 MB.', 400)

    content_type = file.content_type or 'application/octet-stream'
    if content_type not in _ALLOWED_TYPES:
        return jsonify({
            'is_medical': False,
            'document_type': 'unsupported',
            'confidence': 0.0,
            'message': f'Unsupported file type ({content_type}). Please upload an image (PNG, JPG) or PDF.',
            'filename': file.filename,
        })

    # Optional: patient info for cross-verification
    patient_name = request.form.get('patient_name', '')
    patient_dob = request.form.get('patient_dob', '')

    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        # Can't validate without Gemini — allow through
        return jsonify({
            'is_medical': True,
            'document_type': 'unknown',
            'confidence': 0.5,
            'message': 'Document accepted (AI validation unavailable).',
            'filename': file.filename,
            'patient_match': None,
        })

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        b64 = base64.b64encode(contents).decode()

        # Enhanced prompt with patient verification
        patient_check_section = ''
        if patient_name or patient_dob:
            patient_check_section = (
                '\n\nCRITICAL PATIENT VERIFICATION:\n'
                f'The document MUST belong to this patient: "{patient_name}"'
                + (f' (DOB: {patient_dob})' if patient_dob else '') + '\n'
                'Search the ENTIRE document for ANY patient name, date of birth, or identifying information.\n'
                'Compare what you find against the expected patient above.\n'
                'If the document contains a DIFFERENT patient name, this is a MISMATCH and must be flagged.\n'
                'Add to your JSON response:\n'
                '  "document_patient_name": "exact name found in document or null if none found",\n'
                '  "document_patient_dob": "DOB found in document or null",\n'
                '  "patient_match": "match" | "mismatch" | "not_found",\n'
                '  "mismatch_reason": "clear explanation if mismatch, otherwise null"\n'
                '\nRules:\n'
                '- If document shows a different name than expected → "mismatch"\n'
                '- If document name matches (even partial/similar) → "match"\n'
                '- If no patient name found in document → "not_found"\n'
            )

        prompt = (
            'Analyze this document carefully. Determine:\n'
            '1. Is this a medical/healthcare document? Be STRICT — reject receipts, invoices, '
            'random photos, screenshots, memes, non-medical forms, etc.\n'
            '2. If it IS medical, classify it precisely.\n\n'
            'Respond with ONLY a valid JSON object (no markdown, no code fences):\n'
            '{\n'
            '  "is_medical": true/false,\n'
            '  "document_type": "medical_record" | "lab_report" | "prescription" | '
            '"insurance_form" | "referral_letter" | "radiology_report" | "surgical_note" | "non_medical",\n'
            '  "confidence": 0.0 to 1.0,\n'
            '  "brief_description": "one sentence about what this document actually is",\n'
            '  "rejection_reason": "clear reason why this is NOT a medical document (if not medical, otherwise null)"'
            + patient_check_section +
            '\n}'
        )

        response = model.generate_content([
            prompt,
            {'mime_type': content_type, 'data': b64},
        ])

        raw = response.text.strip() if response.text else ''
        parsed = _parse_gemini_json(raw)

        is_medical = parsed.get('is_medical', False)
        doc_type = parsed.get('document_type', 'unknown')
        confidence = float(parsed.get('confidence', 0.0))
        description = parsed.get('brief_description', '')
        rejection_reason = parsed.get('rejection_reason')
        patient_match = parsed.get('patient_match')
        doc_patient_name = parsed.get('document_patient_name')
        doc_patient_dob = parsed.get('document_patient_dob')
        mismatch_reason = parsed.get('mismatch_reason')

        # Strict rejection for non-medical documents
        if not is_medical or confidence < 0.5 or doc_type == 'non_medical':
            reason = rejection_reason or description or 'Not a medical document'
            message = (
                f'REJECTED: This is not a medical document. '
                f'Detected: {reason}. '
                f'Please upload clinical records, lab reports, prescriptions, imaging reports, or other healthcare documents.'
            )
            return jsonify({
                'is_medical': False,
                'document_type': doc_type,
                'confidence': round(confidence, 2),
                'message': message,
                'filename': file.filename,
                'rejection_reason': reason,
                'patient_match': None,
            })

        # Patient name/DOB verification
        patient_match_result = None
        if patient_name or patient_dob:
            if patient_match == 'mismatch':
                # Hard reject — document belongs to a different patient
                mismatch_msg = mismatch_reason or 'Patient name in document does not match.'
                return jsonify({
                    'is_medical': True,
                    'document_type': doc_type,
                    'confidence': round(confidence, 2),
                    'message': f'REJECTED: Document belongs to a different patient. {mismatch_msg}',
                    'filename': file.filename,
                    'patient_match': {
                        'status': 'mismatch',
                        'document_patient_name': doc_patient_name,
                        'document_patient_dob': doc_patient_dob,
                        'reason': mismatch_msg,
                    },
                    'is_medical': False,  # Override — treat as invalid for this patient
                })
            elif patient_match == 'match':
                patient_match_result = {
                    'status': 'match',
                    'document_patient_name': doc_patient_name,
                    'document_patient_dob': doc_patient_dob,
                }
            else:
                patient_match_result = {
                    'status': 'not_found',
                    'reason': 'Could not find patient identifying information in the document.',
                }

        label = _DOC_TYPE_LABELS.get(doc_type, doc_type.replace('_', ' ').title())
        message = f'Valid medical document: {label}.'
        if description:
            message += f' {description}'

        return jsonify({
            'is_medical': True,
            'document_type': doc_type,
            'confidence': round(confidence, 2),
            'message': message,
            'filename': file.filename,
            'patient_match': patient_match_result,
        })

    except Exception as exc:
        # On error, allow through rather than blocking
        return jsonify({
            'is_medical': True,
            'document_type': 'unknown',
            'confidence': 0.5,
            'message': 'Document accepted (validation could not complete).',
            'filename': file.filename,
            'patient_match': None,
        })


@bp.route('/extract', methods=['POST'])
def extract_text_from_document():
    """Upload an image or PDF and extract text using Gemini Vision.

    Returns:
        extracted_text: the raw text
        document_type: detected category (e.g. "medical_record", "lab_report", "non_medical")
        is_medical: True if the document appears to be medical/clinical
        warning: optional warning message if the document is not medical
    """
    db = SessionLocal()
    try:
        user = get_current_user(db)
    finally:
        db.close()

    if 'file' not in request.files:
        raise AppError('No file uploaded', 400)

    file = request.files['file']
    if not file.filename:
        raise AppError('Empty filename', 400)

    contents = file.read()
    if len(contents) == 0:
        raise AppError('Empty file', 400)
    if len(contents) > _MAX_SIZE:
        raise AppError('File too large. Max 10 MB.', 400)

    content_type = file.content_type or 'application/octet-stream'
    if content_type not in _ALLOWED_TYPES:
        raise AppError(
            f'Unsupported file type: {content_type}. Upload an image (PNG, JPG, WEBP) or PDF.',
            400,
        )

    b64 = base64.b64encode(contents).decode()

    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise AppError('Gemini API key not configured', 503)

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        prompt = (
            'You are a medical document analysis system. Analyze this document and respond with ONLY a valid JSON object (no markdown, no code fences).\n\n'
            'Tasks:\n'
            '1. Extract ALL text from the document exactly as it appears.\n'
            '2. Classify the document into one of these categories:\n'
            '   - "medical_record" — patient charts, clinical notes, discharge summaries\n'
            '   - "lab_report" — blood tests, pathology, imaging reports\n'
            '   - "prescription" — medication orders, prescriptions\n'
            '   - "insurance_form" — claim forms, prior auth forms, insurance documents\n'
            '   - "referral_letter" — specialist referrals\n'
            '   - "radiology_report" — X-ray, MRI, CT scan reports\n'
            '   - "surgical_note" — operative notes, surgical reports\n'
            '   - "non_medical" — any document that is NOT related to healthcare\n'
            '3. Rate your confidence that this is a medical document from 0.0 to 1.0.\n\n'
            'Return JSON:\n'
            '{\n'
            '  "extracted_text": "full text here",\n'
            '  "document_type": "category",\n'
            '  "medical_confidence": 0.95,\n'
            '  "brief_summary": "1-2 sentence summary of what the document contains"\n'
            '}'
        )

        response = model.generate_content([
            prompt,
            {'mime_type': content_type, 'data': b64},
        ])

        raw = response.text.strip() if response.text else ''

        # Parse Gemini JSON response
        parsed = _parse_gemini_json(raw)

        extracted = parsed.get('extracted_text', raw)
        doc_type = parsed.get('document_type', 'unknown')
        confidence = float(parsed.get('medical_confidence', 0.5))
        summary = parsed.get('brief_summary', '')

        is_medical = doc_type != 'non_medical' and confidence >= 0.4

        result = {
            'extracted_text': extracted,
            'filename': file.filename,
            'document_type': doc_type,
            'medical_confidence': round(confidence, 2),
            'is_medical': is_medical,
            'summary': summary,
        }

        if not is_medical:
            result['warning'] = (
                'This document does not appear to be a medical or healthcare-related document. '
                f'Detected type: {doc_type.replace("_", " ").title()}. '
                'Please upload a clinical document such as a medical record, lab report, '
                'prescription, or insurance form for prior authorization processing.'
            )

        return jsonify(result)

    except ImportError:
        raise AppError('google-generativeai package not installed', 503)
    except Exception as exc:
        raise AppError(f'OCR extraction failed: {str(exc)}', 500)


def _parse_gemini_json(raw: str) -> dict:
    """Best-effort parse of Gemini response as JSON, stripping markdown fences."""
    text = raw.strip()
    # Strip ```json ... ``` fences
    if text.startswith('```'):
        lines = text.split('\n')
        lines = lines[1:]  # drop opening fence
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {'extracted_text': raw}
