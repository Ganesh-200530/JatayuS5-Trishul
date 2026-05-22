from __future__ import annotations

import os
import uuid
import threading
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, send_from_directory, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models.prior_auth import PriorAuthRequest, PAStatus
from app.models.patient import Patient
from app.models.user import User
from app.models.intake_link import PatientIntakeLink, IntakeLinkStatus
from app.schemas.prior_auth import PriorAuthCreate, PriorAuthRead, PriorAuthUpdate, PriorAuthListRead
from app.schemas.clinical_evidence import ClinicalEvidenceRead
from app.core.security import get_current_user
from app.core.exceptions import EntityNotFound
from app.services.audit import log_action
from app.services.notifications import notify_missing_documents

bp = Blueprint('prior_auth', __name__)


def _run_pipeline(pa_id: str, clinical_notes: str | None):
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
        orchestrator.run_full_pipeline(pa, clinical_notes)
    finally:
        db.close()


@bp.route('/', methods=['POST'])
def create_prior_auth():
    data = request.get_json()
    payload = PriorAuthCreate(**data)
    db = SessionLocal()
    try:
        user = get_current_user(db)
        patient = db.execute(select(Patient).where(Patient.id == str(payload.patient_id))).scalar_one_or_none()
        if not patient:
            raise EntityNotFound('Patient', str(payload.patient_id))

        pa = PriorAuthRequest(
            patient_id=str(payload.patient_id),
            cpt_code=payload.cpt_code,
            cpt_description=payload.cpt_description,
            icd10_codes=payload.icd10_codes,
            ordering_provider_npi=payload.ordering_provider_npi or f'NPI-{uuid.uuid4().hex[:10].upper()}',
            ordering_provider_name=payload.ordering_provider_name,
            facility_npi=payload.facility_npi,
            facility_name=payload.facility_name,
            payer_id=payload.payer_id,
            payer_name=payload.payer_name,
            urgency=payload.urgency,
        )
        db.add(pa)
        db.flush()
        log_action(
            db, entity_type='prior_auth_request', entity_id=pa.id,
            action='created', actor=user.email,
            details={'cpt': payload.cpt_code, 'payer': payload.payer_id},
        )
        db.commit()
        db.refresh(pa)
        result_data = PriorAuthRead.model_validate(pa, from_attributes=True).model_dump(mode='json')

        # Kick off pipeline in background thread
        clinical_notes = payload.clinical_notes if hasattr(payload, 'clinical_notes') else None
        t = threading.Thread(target=_run_pipeline, args=(pa.id, clinical_notes), daemon=True)
        t.start()

        return jsonify(result_data), 201
    finally:
        db.close()


@bp.route('/', methods=['GET'])
def list_prior_auths():
    db = SessionLocal()
    try:
        user = get_current_user(db)
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 50, type=int)
        status_filter = request.args.get('status')
        payer_id = request.args.get('payer_id')
        requires_review = request.args.get('requires_review')

        query = select(PriorAuthRequest)
        if status_filter:
            query = query.where(PriorAuthRequest.status == status_filter)
        if payer_id:
            query = query.where(PriorAuthRequest.payer_id == payer_id)
        if requires_review is not None:
            query = query.where(PriorAuthRequest.requires_human_review == (requires_review == 'true'))
        query = query.order_by(PriorAuthRequest.created_at.desc()).offset(skip).limit(limit)
        result = db.execute(query)
        items = list(result.scalars().all())

        # Fetch patient names
        patient_ids = list({i.patient_id for i in items})
        patient_names = {}
        if patient_ids:
            patients = db.execute(select(Patient).where(Patient.id.in_(patient_ids))).scalars().all()
            patient_names = {p.id: f"{p.first_name} {p.last_name}" for p in patients}

        out = []
        for i in items:
            d = PriorAuthListRead.model_validate(i, from_attributes=True).model_dump(mode='json')
            d['patient_name'] = patient_names.get(i.patient_id)
            out.append(d)
        return jsonify(out)
    finally:
        db.close()


@bp.route('/<pa_id>', methods=['GET'])
def get_prior_auth(pa_id):
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(PriorAuthRequest).where(PriorAuthRequest.id == str(pa_id)))
        pa = result.scalar_one_or_none()
        if not pa:
            raise EntityNotFound('PriorAuthRequest', pa_id)
        return jsonify(PriorAuthRead.model_validate(pa, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()


@bp.route('/<pa_id>/evidence', methods=['GET'])
def get_evidence(pa_id):
    db = SessionLocal()
    try:
        user = get_current_user(db)
        from app.models.clinical_evidence import ClinicalEvidence
        result = db.execute(select(ClinicalEvidence).where(ClinicalEvidence.prior_auth_id == str(pa_id)))
        evidence = result.scalar_one_or_none()
        if not evidence:
            return jsonify(None), 204
        return jsonify(ClinicalEvidenceRead.model_validate(evidence, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()


@bp.route('/<pa_id>/breakdown', methods=['GET'])
def get_decision_breakdown(pa_id):
    """Get a structured breakdown of evidence vs policy criteria."""
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(PriorAuthRequest).where(PriorAuthRequest.id == str(pa_id)))
        pa = result.scalar_one_or_none()
        if not pa:
            raise EntityNotFound('PriorAuthRequest', pa_id)

        from app.models.clinical_evidence import ClinicalEvidence
        evidence = db.execute(select(ClinicalEvidence).where(ClinicalEvidence.prior_auth_id == str(pa_id))).scalar_one_or_none()

        if not evidence:
            return jsonify({'criteria_met': [], 'criteria_not_met': [], 'overall_score': 0, 'message': 'No evidence extracted yet'}), 200

        # Build breakdown from evidence fields
        criteria_met = []
        criteria_not_met = []

        if evidence.diagnosis_summary:
            criteria_met.append({'criterion': 'Diagnosis Documentation', 'evidence_found': evidence.diagnosis_summary[:200], 'source': 'Clinical Notes'})
        else:
            criteria_not_met.append({'criterion': 'Diagnosis Documentation', 'reason_missing': 'No diagnosis summary extracted from records'})

        if evidence.medical_necessity_justification:
            criteria_met.append({'criterion': 'Medical Necessity Justification', 'evidence_found': evidence.medical_necessity_justification[:200], 'source': 'Clinical Notes'})
        else:
            criteria_not_met.append({'criterion': 'Medical Necessity Justification', 'reason_missing': 'No medical necessity justification found'})

        if evidence.treatment_history and len(evidence.treatment_history) > 0:
            criteria_met.append({'criterion': 'Treatment History', 'evidence_found': f'{len(evidence.treatment_history)} treatments documented', 'source': 'Patient Records'})
        else:
            criteria_not_met.append({'criterion': 'Treatment History', 'reason_missing': 'No prior treatment history documented'})

        if evidence.failed_conservative_therapies and len(evidence.failed_conservative_therapies) > 0:
            criteria_met.append({'criterion': 'Failed Conservative Therapies', 'evidence_found': f'{len(evidence.failed_conservative_therapies)} failed therapies documented', 'source': 'Clinical Notes'})
        else:
            criteria_not_met.append({'criterion': 'Failed Conservative Therapies', 'reason_missing': 'No documentation of failed conservative treatments'})

        if evidence.supporting_findings and len(evidence.supporting_findings) > 0:
            criteria_met.append({'criterion': 'Supporting Clinical Findings', 'evidence_found': f'{len(evidence.supporting_findings)} findings documented', 'source': 'Clinical Records'})
        else:
            criteria_not_met.append({'criterion': 'Supporting Clinical Findings', 'reason_missing': 'No supporting clinical findings extracted'})

        if evidence.relevant_lab_results and len(evidence.relevant_lab_results) > 0:
            criteria_met.append({'criterion': 'Lab Results', 'evidence_found': f'{len(evidence.relevant_lab_results)} lab results available', 'source': 'Lab Reports'})

        if evidence.relevant_imaging and len(evidence.relevant_imaging) > 0:
            criteria_met.append({'criterion': 'Imaging Results', 'evidence_found': f'{len(evidence.relevant_imaging)} imaging studies available', 'source': 'Radiology'})

        total = len(criteria_met) + len(criteria_not_met)
        overall_score = len(criteria_met) / total if total > 0 else 0

        return jsonify({
            'criteria_met': criteria_met,
            'criteria_not_met': criteria_not_met,
            'overall_score': round(overall_score, 2),
            'total_criteria': total,
            'met_count': len(criteria_met),
            'not_met_count': len(criteria_not_met),
        })
    finally:
        db.close()


@bp.route('/<pa_id>', methods=['PATCH'])
def update_prior_auth(pa_id):
    data = request.get_json()
    payload = PriorAuthUpdate(**data)
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(PriorAuthRequest).where(PriorAuthRequest.id == str(pa_id)))
        pa = result.scalar_one_or_none()
        if not pa:
            raise EntityNotFound('PriorAuthRequest', pa_id)
        old_status = pa.status.value
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(pa, field, value)
        log_action(
            db, entity_type='prior_auth_request', entity_id=pa.id,
            action='updated', actor=user.email,
            previous_state=old_status,
            new_state=pa.status.value if payload.status else old_status,
        )
        db.commit()
        db.refresh(pa)
        return jsonify(PriorAuthRead.model_validate(pa, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()


@bp.route('/<pa_id>/review', methods=['POST'])
def human_review_decision(pa_id):
    data = request.get_json(silent=True) or {}
    decision = data.get('decision') or request.args.get('decision')
    reason = data.get('reason') or request.args.get('reason')
    db = SessionLocal()
    try:
        user = get_current_user(db)
        if user.role not in ('admin', 'reviewer'):
            from app.core.exceptions import Forbidden
            raise Forbidden("Insufficient permissions")
        result = db.execute(select(PriorAuthRequest).where(PriorAuthRequest.id == str(pa_id)))
        pa = result.scalar_one_or_none()
        if not pa:
            raise EntityNotFound('PriorAuthRequest', pa_id)
        old_status = pa.status.value
        if decision == 'approve':
            pa.status = PAStatus.APPROVED
            pa.decision_reason = reason or 'Approved by human reviewer'
        elif decision == 'deny':
            pa.status = PAStatus.DENIED
            pa.decision_reason = reason or 'Denied by human reviewer'
        else:
            return jsonify({'detail': "Decision must be 'approve' or 'deny'"}), 400
        pa.requires_human_review = False
        pa.human_review_reason = None
        from datetime import datetime, timezone
        pa.decision_date = datetime.now(timezone.utc)
        log_action(
            db, entity_type='prior_auth_request', entity_id=pa.id,
            action='human_review_' + decision, actor=user.email,
            previous_state=old_status, new_state=pa.status.value,
        )
        db.commit()
        return jsonify({'message': f'PA {decision}d', 'prior_auth_id': pa_id, 'new_status': pa.status.value})
    finally:
        db.close()


@bp.route('/<pa_id>/retry', methods=['POST'])
def retry_pipeline(pa_id):
    data = request.get_json(silent=True) or {}
    clinical_notes = data.get('clinical_notes')
    db = SessionLocal()
    try:
        user = get_current_user(db)
        if user.role not in ('admin', 'reviewer'):
            from app.core.exceptions import Forbidden
            raise Forbidden("Insufficient permissions")
        result = db.execute(select(PriorAuthRequest).where(PriorAuthRequest.id == str(pa_id)))
        pa = result.scalar_one_or_none()
        if not pa:
            raise EntityNotFound('PriorAuthRequest', pa_id)

        # Fall back to metadata clinical_notes if not provided in request body
        if not clinical_notes and pa.metadata_ and isinstance(pa.metadata_, dict):
            clinical_notes = pa.metadata_.get('clinical_notes')

        pa.status = PAStatus.INITIATED
        pa.requires_human_review = False
        pa.human_review_reason = None
        db.commit()
        t = threading.Thread(target=_run_pipeline, args=(str(pa_id), clinical_notes), daemon=True)
        t.start()
        return jsonify({'message': 'Pipeline retry initiated', 'prior_auth_id': pa_id})
    finally:
        db.close()


@bp.route('/<pa_id>/evaluate', methods=['POST'])
def start_ai_evaluation(pa_id):
    """Manually start AI evaluation for intake-received PA requests."""
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(PriorAuthRequest).where(PriorAuthRequest.id == str(pa_id)))
        pa = result.scalar_one_or_none()
        if not pa:
            raise EntityNotFound('PriorAuthRequest', pa_id)
        if pa.status != PAStatus.INTAKE_RECEIVED:
            return jsonify({'detail': 'AI evaluation can only be started for intake-received requests.'}), 400

        # Extract clinical notes from metadata
        clinical_notes = None
        if pa.metadata_ and isinstance(pa.metadata_, dict):
            clinical_notes = pa.metadata_.get('clinical_notes')

        pa.status = PAStatus.INITIATED
        log_action(
            db, entity_type='prior_auth_request', entity_id=pa.id,
            action='ai_evaluation_started', actor=user.email,
            previous_state='intake_received', new_state='initiated',
        )
        db.commit()

        t = threading.Thread(target=_run_pipeline, args=(pa.id, clinical_notes), daemon=True)
        t.start()
        return jsonify({'message': 'AI evaluation started', 'prior_auth_id': pa_id})
    finally:
        db.close()


_DOC_LINK_EXPIRY_DAYS = 7


@bp.route('/<pa_id>/request-documents', methods=['POST'])
def request_missing_documents(pa_id):
    """Generate a patient link to upload missing documents for an existing PA."""
    data = request.get_json(silent=True) or {}
    missing_docs = data.get('missing_documents', [])
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(PriorAuthRequest).where(PriorAuthRequest.id == str(pa_id)))
        pa = result.scalar_one_or_none()
        if not pa:
            raise EntityNotFound('PriorAuthRequest', pa_id)

        # Expire any existing active additional-doc links for this PA
        existing = db.execute(
            select(PatientIntakeLink).where(
                PatientIntakeLink.prior_auth_id == str(pa_id),
                PatientIntakeLink.status == IntakeLinkStatus.ACTIVE,
            )
        ).scalars().all()
        for old in existing:
            old.status = IntakeLinkStatus.EXPIRED

        link = PatientIntakeLink(
            patient_id=pa.patient_id,
            prior_auth_id=str(pa_id),
            missing_documents=missing_docs,
            expires_at=datetime.utcnow() + timedelta(days=_DOC_LINK_EXPIRY_DAYS),
        )
        db.add(link)

        # Store the request in PA metadata
        meta = dict(pa.metadata_) if pa.metadata_ else {}
        meta['documents_requested'] = True
        meta['documents_requested_at'] = datetime.utcnow().isoformat()
        meta['missing_documents'] = missing_docs
        pa.metadata_ = meta

        log_action(
            db, entity_type='prior_auth_request', entity_id=pa.id,
            action='documents_requested', actor=user.email,
            details={'missing_documents': missing_docs},
        )
        db.commit()
        db.refresh(link)

        # Notify patient of missing documents
        patient = db.execute(select(Patient).where(Patient.id == pa.patient_id)).scalar_one_or_none()
        if patient and patient.email:
            upload_url = f"/intake/{link.token}"
            notify_missing_documents(
                patient.email,
                f"{patient.first_name} {patient.last_name}",
                missing_docs,
                upload_url,
            )

        return jsonify({
            'intake_token': link.token,
            'expires_at': link.expires_at.isoformat(),
            'missing_documents': missing_docs,
        }), 201
    finally:
        db.close()


@bp.route('/<pa_id>/additional-documents', methods=['GET'])
def get_additional_documents(pa_id):
    """Check if there are pending document request links for a PA."""
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(PriorAuthRequest).where(PriorAuthRequest.id == str(pa_id)))
        pa = result.scalar_one_or_none()
        if not pa:
            raise EntityNotFound('PriorAuthRequest', pa_id)

        links = db.execute(
            select(PatientIntakeLink).where(
                PatientIntakeLink.prior_auth_id == str(pa_id),
            ).order_by(PatientIntakeLink.created_at.desc())
        ).scalars().all()

        return jsonify([{
            'token': lnk.token,
            'status': lnk.status.value,
            'missing_documents': lnk.missing_documents,
            'expires_at': lnk.expires_at.isoformat(),
            'created_at': lnk.created_at.isoformat() if lnk.created_at else None,
        } for lnk in links])
    finally:
        db.close()


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads')


@bp.route('/<pa_id>/stream', methods=['GET'])
def stream_pipeline(pa_id):
    """SSE endpoint for real-time pipeline progress updates."""
    from app.services.sse import stream
    return Response(stream(pa_id), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@bp.route('/<pa_id>/export-pdf', methods=['GET'])
def export_pdf(pa_id):
    """Generate and return a PDF summary of a prior authorization request."""
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch

    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(
            select(PriorAuthRequest)
            .options(selectinload(PriorAuthRequest.patient))
            .where(PriorAuthRequest.id == str(pa_id))
        )
        pa = result.scalar_one_or_none()
        if not pa:
            raise EntityNotFound('PriorAuthRequest', pa_id)

        from app.models.clinical_evidence import ClinicalEvidence
        evidence = db.execute(
            select(ClinicalEvidence).where(ClinicalEvidence.prior_auth_id == str(pa_id))
        ).scalar_one_or_none()

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('TitleBlue', parent=styles['Title'], textColor=colors.HexColor('#1e40af'), fontSize=18)
        heading_style = ParagraphStyle('HeadBlue', parent=styles['Heading2'], textColor=colors.HexColor('#1e40af'))
        normal = styles['Normal']
        small = ParagraphStyle('Small', parent=normal, fontSize=8, textColor=colors.grey)

        elements = []

        # Header
        elements.append(Paragraph('MEDIX — Prior Authorization Report', title_style))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f'Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}', small))
        elements.append(Spacer(1, 12))

        # Patient info
        patient = pa.patient
        if patient:
            elements.append(Paragraph('Patient Information', heading_style))
            pdata = [
                ['Name', f'{patient.first_name} {patient.last_name}'],
                ['MRN', patient.mrn],
                ['DOB', str(patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else 'N/A')],
                ['Gender', patient.gender],
                ['Payer', patient.payer_name or patient.payer_id],
            ]
            if patient.subscriber_id:
                pdata.append(['Subscriber ID', patient.subscriber_id])
            t = Table(pdata, colWidths=[1.5 * inch, 5 * inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eff6ff')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dbeafe')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 12))

        # PA details
        elements.append(Paragraph('Authorization Details', heading_style))
        pa_data = [
            ['PA ID', str(pa.id)],
            ['Status', pa.status.value.upper()],
            ['CPT Code', pa.cpt_code or 'N/A'],
            ['CPT Description', pa.cpt_description or 'N/A'],
            ['Provider', pa.ordering_provider_name or pa.ordering_provider_npi or 'N/A'],
            ['Urgency', pa.urgency.value if pa.urgency else 'standard'],
            ['Created', pa.created_at.strftime('%Y-%m-%d %H:%M UTC') if pa.created_at else 'N/A'],
        ]
        if pa.confidence_score is not None:
            pa_data.append(['AI Confidence', f'{pa.confidence_score:.0%}'])
        if pa.decision_reason:
            pa_data.append(['Decision', Paragraph(pa.decision_reason, normal)])
        if pa.decision_date:
            pa_data.append(['Decision Date', pa.decision_date.strftime('%Y-%m-%d %H:%M UTC')])
        t = Table(pa_data, colWidths=[1.5 * inch, 5 * inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eff6ff')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dbeafe')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))

        # Clinical evidence
        if evidence:
            elements.append(Paragraph('Clinical Evidence', heading_style))
            ev_data = []
            if evidence.diagnosis_summary:
                ev_data.append(['Diagnosis', Paragraph(str(evidence.diagnosis_summary), normal)])
            if evidence.medical_necessity_justification:
                ev_data.append(['Medical Necessity', Paragraph(str(evidence.medical_necessity_justification), normal)])
            if evidence.supporting_findings:
                findings = evidence.supporting_findings
                if isinstance(findings, list):
                    findings = ', '.join(str(f) for f in findings)
                ev_data.append(['Supporting Findings', Paragraph(str(findings), normal)])
            if evidence.failed_conservative_therapies:
                therapies = evidence.failed_conservative_therapies
                if isinstance(therapies, list):
                    therapies = ', '.join(str(t) for t in therapies)
                ev_data.append(['Failed Therapies', Paragraph(str(therapies), normal)])
            if ev_data:
                t = Table(ev_data, colWidths=[1.5 * inch, 5 * inch])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0fdf4')),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bbf7d0')),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                elements.append(t)
            elements.append(Spacer(1, 12))

        # Documents summary
        meta = pa.metadata_ or {}
        docs = meta.get('documents', [])
        if docs and isinstance(docs, list):
            elements.append(Paragraph('Uploaded Documents', heading_style))
            doc_data = [['#', 'Filename', 'Type', 'Language']]
            for i, d in enumerate(docs, 1):
                if isinstance(d, dict):
                    doc_data.append([
                        str(i),
                        d.get('filename', 'N/A'),
                        d.get('document_type', 'unknown'),
                        d.get('language', 'English'),
                    ])
            t = Table(doc_data, colWidths=[0.4 * inch, 2.8 * inch, 1.8 * inch, 1.5 * inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dbeafe')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 12))

        # Footer
        elements.append(Spacer(1, 24))
        elements.append(Paragraph('This report was generated by MEDIX PA Automation Platform.', small))

        doc.build(elements)
        buf.seek(0)

        safe_id = str(pa_id).replace('-', '')[:12]
        return Response(
            buf.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="PA_Report_{safe_id}.pdf"'},
        )
    finally:
        db.close()


@bp.route('/documents/<file_id>', methods=['GET'])
def serve_document(file_id):
    """Serve an uploaded document file by its file_id.
    Supports both Authorization header and ?token= query param (for new tab viewing).
    """
    from app.core.security import decode_token
    db = SessionLocal()
    try:
        # Accept token from header OR query param
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
        else:
            token = request.args.get('token', '')
        if not token:
            return jsonify({"error": "Authentication required"}), 401
        try:
            decode_token(token)
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Validate file_id is a safe filename (UUID + extension only)
        safe_chars = set('abcdefghijklmnopqrstuvwxyz0123456789-.')
        if not all(c in safe_chars for c in file_id.lower()) or '..' in file_id or '/' in file_id or '\\' in file_id:
            return jsonify({"error": "Invalid file ID"}), 400
        file_path = os.path.join(UPLOAD_DIR, file_id)
        if not os.path.isfile(file_path):
            return jsonify({"error": "Document not found"}), 404
        return send_from_directory(UPLOAD_DIR, file_id, as_attachment=False)
    finally:
        db.close()
