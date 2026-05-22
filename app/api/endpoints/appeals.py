from __future__ import annotations

"""Appeal endpoints -- create, list, submit."""

import uuid
import threading

from flask import Blueprint, request, jsonify
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models.prior_auth import PriorAuthRequest
from app.models.appeal import Appeal
from app.models.clinical_evidence import ClinicalEvidence
from app.schemas.appeal import AppealCreate, AppealRead
from app.core.security import get_current_user
from app.core.exceptions import EntityNotFound

bp = Blueprint('appeals', __name__)


def _run_appeal(pa_id, denial_reason, denial_details, denial_code):
    db = SessionLocal()
    try:
        result = db.execute(
            select(PriorAuthRequest)
            .options(selectinload(PriorAuthRequest.patient))
            .where(PriorAuthRequest.id == pa_id)
        )
        pa = result.scalar_one_or_none()
        if not pa:
            return
        from app.agents.orchestrator import Orchestrator
        orchestrator = Orchestrator(db)
        orchestrator.handle_denial(pa, denial_reason, denial_details, denial_code)
    finally:
        db.close()


@bp.route('/', methods=['POST'])
def initiate_appeal():
    """Initiate an appeal for a denied PA request."""
    data = request.get_json()
    payload = AppealCreate(**data)
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(
            select(PriorAuthRequest).where(PriorAuthRequest.id == str(payload.prior_auth_id))
        )
        pa = result.scalar_one_or_none()
        if not pa:
            raise EntityNotFound('PriorAuthRequest', str(payload.prior_auth_id))

        t = threading.Thread(
            target=_run_appeal,
            args=(str(payload.prior_auth_id), payload.denial_reason.value, payload.denial_details or '', payload.denial_code),
            daemon=True,
        )
        t.start()

        return jsonify({'message': 'Appeal process initiated', 'prior_auth_id': str(payload.prior_auth_id)}), 202
    finally:
        db.close()


@bp.route('/', methods=['GET'])
def list_appeals():
    db = SessionLocal()
    try:
        user = get_current_user(db)
        prior_auth_id = request.args.get('prior_auth_id')
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 50, type=int)
        query = select(Appeal)
        if prior_auth_id:
            query = query.where(Appeal.prior_auth_id == str(prior_auth_id))
        query = query.order_by(Appeal.created_at.desc()).offset(skip).limit(limit)
        result = db.execute(query)
        items = list(result.scalars().all())

        # Enrich with patient info from prior auth requests
        pa_ids = list({a.prior_auth_id for a in items})
        pa_map = {}
        if pa_ids:
            from app.models.patient import Patient
            pas = db.execute(
                select(PriorAuthRequest).where(PriorAuthRequest.id.in_(pa_ids))
            ).scalars().all()
            patient_ids = list({pa.patient_id for pa in pas})
            patients = {}
            if patient_ids:
                pts = db.execute(select(Patient).where(Patient.id.in_(patient_ids))).scalars().all()
                patients = {p.id: p for p in pts}
            for pa in pas:
                pt = patients.get(pa.patient_id)
                pa_map[pa.id] = {
                    'patient_name': f"{pt.first_name} {pt.last_name}" if pt else None,
                    'patient_mrn': pt.mrn if pt else None,
                    'cpt_code': pa.cpt_code,
                    'payer_name': pa.payer_name or pa.payer_id,
                }

        out = []
        for i in items:
            d = AppealRead.model_validate(i, from_attributes=True).model_dump(mode='json')
            pa_info = pa_map.get(i.prior_auth_id, {})
            d['patient_name'] = pa_info.get('patient_name')
            d['patient_mrn'] = pa_info.get('patient_mrn')
            d['cpt_code'] = pa_info.get('cpt_code')
            d['payer_name'] = pa_info.get('payer_name')
            out.append(d)
        return jsonify(out)
    finally:
        db.close()


@bp.route('/<appeal_id>', methods=['GET'])
def get_appeal(appeal_id):
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(Appeal).where(Appeal.id == str(appeal_id)))
        appeal = result.scalar_one_or_none()
        if not appeal:
            raise EntityNotFound('Appeal', appeal_id)
        return jsonify(AppealRead.model_validate(appeal, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()


@bp.route('/<appeal_id>/letter', methods=['PATCH'])
def update_appeal_letter(appeal_id):
    """Update the appeal letter text (admin editing)."""
    db = SessionLocal()
    try:
        user = get_current_user(db)
        data = request.get_json()
        new_letter = data.get('appeal_letter')
        if not new_letter:
            return jsonify({'detail': 'appeal_letter is required'}), 400

        result = db.execute(select(Appeal).where(Appeal.id == str(appeal_id)))
        appeal = result.scalar_one_or_none()
        if not appeal:
            raise EntityNotFound('Appeal', appeal_id)

        appeal.appeal_letter = new_letter
        db.commit()
        return jsonify({'message': 'Appeal letter updated', 'id': appeal_id})
    finally:
        db.close()


@bp.route('/<appeal_id>/pdf', methods=['GET'])
def download_appeal_pdf(appeal_id):
    """Generate and download the appeal letter as a PDF."""
    from flask import send_file
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.enums import TA_LEFT
    import io

    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(Appeal).where(Appeal.id == str(appeal_id)))
        appeal = result.scalar_one_or_none()
        if not appeal:
            raise EntityNotFound('Appeal', appeal_id)

        if not appeal.appeal_letter:
            return jsonify({'detail': 'No appeal letter content to export'}), 400

        # Generate PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='LetterBody',
            parent=styles['Normal'],
            fontSize=11,
            leading=16,
            spaceAfter=12,
            alignment=TA_LEFT,
        ))
        styles.add(ParagraphStyle(
            name='LetterHeader',
            parent=styles['Normal'],
            fontSize=12,
            leading=16,
            spaceAfter=6,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
        ))

        story = []

        # Title
        story.append(Paragraph("APPEAL LETTER", styles['Title']))
        story.append(Spacer(1, 0.3 * inch))

        # Letter content — split by paragraphs
        letter_text = appeal.appeal_letter
        paragraphs = letter_text.split('\n')
        for para in paragraphs:
            para = para.strip()
            if not para:
                story.append(Spacer(1, 0.15 * inch))
            elif para.startswith('RE:') or para.startswith('Re:') or para.startswith('Dear') or para.startswith('Sincerely') or para.startswith('Date:'):
                story.append(Paragraph(para, styles['LetterHeader']))
            else:
                # Escape special characters for ReportLab
                para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(para, styles['LetterBody']))

        # References section
        if appeal.cited_references:
            story.append(Spacer(1, 0.3 * inch))
            story.append(Paragraph("REFERENCES", styles['LetterHeader']))
            for i, ref in enumerate(appeal.cited_references, 1):
                citation = ref.get('citation', str(ref)) if isinstance(ref, dict) else str(ref)
                citation = citation.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(f"{i}. {citation}", styles['LetterBody']))

        doc.build(story)
        buffer.seek(0)

        filename = f"appeal_letter_{appeal_id[:8]}.pdf"
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename,
        )
    finally:
        db.close()
