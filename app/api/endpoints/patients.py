from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
from sqlalchemy import select

from app.database import SessionLocal
from app.models.patient import Patient
from app.models.intake_link import PatientIntakeLink, IntakeLinkStatus
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.core.security import get_current_user
from app.core.exceptions import EntityNotFound, DuplicateEntity
from app.services.fhir import FHIRClient

bp = Blueprint('patients', __name__)

_INTAKE_LINK_EXPIRY_DAYS = 7


def _utcnow():
    return datetime.utcnow()


@bp.route('/', methods=['POST'])
def create_patient():
    data = request.get_json()
    payload = PatientCreate(**data)
    # Auto-generate MRN if not provided
    if not payload.mrn:
        import random, string
        payload.mrn = 'MRN-' + datetime.utcnow().strftime('%Y%m%d') + '-' + ''.join(random.choices(string.digits, k=5))
    db = SessionLocal()
    try:
        user = get_current_user(db)
        existing = db.execute(select(Patient).where(Patient.mrn == payload.mrn)).scalar_one_or_none()
        if existing:
            # Return existing patient with a fresh intake link
            link = PatientIntakeLink(
                patient_id=existing.id,
                expires_at=_utcnow() + timedelta(days=_INTAKE_LINK_EXPIRY_DAYS),
            )
            db.add(link)
            db.commit()
            db.refresh(existing)
            db.refresh(link)
            result = PatientRead.model_validate(existing, from_attributes=True).model_dump(mode='json')
            result['intake_token'] = link.token
            return jsonify(result), 200
        pdata = payload.model_dump()
        if pdata['date_of_birth'].tzinfo is not None:
            pdata['date_of_birth'] = pdata['date_of_birth'].replace(tzinfo=None)
        patient = Patient(**pdata)
        db.add(patient)
        db.flush()

        # Generate intake link
        link = PatientIntakeLink(
            patient_id=patient.id,
            expires_at=_utcnow() + timedelta(days=_INTAKE_LINK_EXPIRY_DAYS),
        )
        db.add(link)
        db.commit()
        db.refresh(patient)
        db.refresh(link)

        result = PatientRead.model_validate(patient, from_attributes=True).model_dump(mode='json')
        result['intake_token'] = link.token
        return jsonify(result), 201
    finally:
        db.close()


@bp.route('/', methods=['GET'])
def list_patients():
    db = SessionLocal()
    try:
        user = get_current_user(db)
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search')
        query = select(Patient)
        if search:
            pattern = f'%{search}%'
            query = query.where(
                (Patient.mrn.ilike(pattern))
                | (Patient.first_name.ilike(pattern))
                | (Patient.last_name.ilike(pattern))
            )
        query = query.order_by(Patient.created_at.desc()).offset(skip).limit(limit)
        result = db.execute(query)
        items = list(result.scalars().all())

        # Attach active intake tokens
        patient_ids = [p.id for p in items]
        active_links = {}
        if patient_ids:
            links = db.execute(
                select(PatientIntakeLink).where(
                    PatientIntakeLink.patient_id.in_(patient_ids),
                    PatientIntakeLink.status == IntakeLinkStatus.ACTIVE,
                )
            ).scalars().all()
            for lnk in links:
                active_links[lnk.patient_id] = lnk.token

        out = []
        for i in items:
            d = PatientRead.model_validate(i, from_attributes=True).model_dump(mode='json')
            d['intake_token'] = active_links.get(i.id)
            out.append(d)
        return jsonify(out)
    finally:
        db.close()


@bp.route('/<patient_id>', methods=['GET'])
def get_patient(patient_id):
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(Patient).where(Patient.id == str(patient_id)))
        patient = result.scalar_one_or_none()
        if not patient:
            raise EntityNotFound('Patient', patient_id)
        return jsonify(PatientRead.model_validate(patient, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()


@bp.route('/<patient_id>', methods=['PATCH'])
def update_patient(patient_id):
    data = request.get_json()
    payload = PatientUpdate(**data)
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(Patient).where(Patient.id == str(patient_id)))
        patient = result.scalar_one_or_none()
        if not patient:
            raise EntityNotFound('Patient', patient_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(patient, field, value)
        db.commit()
        db.refresh(patient)
        return jsonify(PatientRead.model_validate(patient, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()


@bp.route('/<patient_id>/intake-link', methods=['POST'])
def generate_intake_link(patient_id):
    """Generate a new intake link for an existing patient."""
    db = SessionLocal()
    try:
        user = get_current_user(db)
        patient = db.execute(select(Patient).where(Patient.id == str(patient_id))).scalar_one_or_none()
        if not patient:
            raise EntityNotFound('Patient', patient_id)

        # Expire any existing active links for this patient
        active_links = db.execute(
            select(PatientIntakeLink).where(
                PatientIntakeLink.patient_id == patient.id,
                PatientIntakeLink.status == IntakeLinkStatus.ACTIVE,
            )
        ).scalars().all()
        for old in active_links:
            old.status = IntakeLinkStatus.EXPIRED

        link = PatientIntakeLink(
            patient_id=patient.id,
            expires_at=_utcnow() + timedelta(days=_INTAKE_LINK_EXPIRY_DAYS),
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        return jsonify({'intake_token': link.token, 'expires_at': link.expires_at.isoformat()}), 201
    finally:
        db.close()


@bp.route('/import-fhir', methods=['POST'])
def import_from_fhir():
    """Import patient demographics from a FHIR server.

    Accepts JSON: { "fhir_patient_id": "...", "payer_id": "...", "payer_name": "..." }
    or: { "mrn": "...", "payer_id": "...", "payer_name": "..." } to search by MRN.
    """
    data = request.get_json(silent=True) or {}
    payer_id = data.get('payer_id', '')
    payer_name = data.get('payer_name', '')

    if not payer_id:
        return jsonify({'detail': 'payer_id is required'}), 400

    db = SessionLocal()
    try:
        user = get_current_user(db)
        fhir = FHIRClient()

        fhir_id = data.get('fhir_patient_id')
        mrn = data.get('mrn')

        if fhir_id:
            fhir_patient = fhir.get_patient(fhir_id)
        elif mrn:
            bundle = fhir.search_patient(mrn)
            entries = bundle.get('entry', [])
            if not entries:
                return jsonify({'detail': f'No FHIR patient found with MRN {mrn}'}), 404
            fhir_patient = entries[0]['resource']
            fhir_id = fhir_patient.get('id')
        else:
            return jsonify({'detail': 'Provide fhir_patient_id or mrn'}), 400

        # Extract demographics from FHIR Patient resource
        names = fhir_patient.get('name', [{}])
        name_obj = names[0] if names else {}
        first_name = ' '.join(name_obj.get('given', ['Unknown']))
        last_name = name_obj.get('family', 'Unknown')
        gender = fhir_patient.get('gender', 'unknown')
        dob_str = fhir_patient.get('birthDate', '')

        # Extract MRN from identifiers if not provided
        if not mrn:
            for ident in fhir_patient.get('identifier', []):
                id_type = ident.get('type', {}).get('coding', [{}])[0].get('code', '')
                if id_type == 'MR':
                    mrn = ident.get('value', '')
                    break
            if not mrn:
                mrn = f'FHIR-{fhir_id}'

        # Extract contact info
        email = ''
        phone = ''
        for telecom in fhir_patient.get('telecom', []):
            if telecom.get('system') == 'email' and not email:
                email = telecom.get('value', '')
            if telecom.get('system') == 'phone' and not phone:
                phone = telecom.get('value', '')

        # Parse DOB
        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d')
            except ValueError:
                try:
                    dob = datetime.strptime(dob_str[:7], '%Y-%m')
                except ValueError:
                    dob = datetime(2000, 1, 1)
        else:
            dob = datetime(2000, 1, 1)

        # Check if patient already exists by MRN
        existing = db.execute(select(Patient).where(Patient.mrn == mrn)).scalar_one_or_none()
        if existing:
            result = PatientRead.model_validate(existing, from_attributes=True).model_dump(mode='json')
            result['fhir_imported'] = False
            result['message'] = 'Patient with this MRN already exists'
            return jsonify(result), 200

        patient = Patient(
            mrn=mrn,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            gender=gender,
            email=email or None,
            phone=phone or None,
            payer_id=payer_id,
            payer_name=payer_name or None,
            fhir_patient_id=fhir_id,
        )
        db.add(patient)
        db.flush()

        # Generate intake link
        link = PatientIntakeLink(
            patient_id=patient.id,
            expires_at=_utcnow() + timedelta(days=_INTAKE_LINK_EXPIRY_DAYS),
        )
        db.add(link)
        db.commit()
        db.refresh(patient)
        db.refresh(link)

        result = PatientRead.model_validate(patient, from_attributes=True).model_dump(mode='json')
        result['intake_token'] = link.token
        result['fhir_imported'] = True
        return jsonify(result), 201
    except Exception as exc:
        err_msg = str(exc)
        if 'ConnectError' in err_msg or 'Connection' in err_msg:
            return jsonify({'detail': 'Could not connect to FHIR server. Check FHIR_BASE_URL configuration.'}), 502
        raise
    finally:
        db.close()
