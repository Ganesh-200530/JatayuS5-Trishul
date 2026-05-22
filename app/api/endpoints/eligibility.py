from __future__ import annotations

"""Eligibility check endpoints."""

import uuid

from flask import Blueprint, request, jsonify
from sqlalchemy import select

from app.database import SessionLocal
from app.models.eligibility import EligibilityCheck, EligibilityStatus
from app.models.patient import Patient
from app.schemas.eligibility import EligibilityCheckRequest, EligibilityCheckResponse
from app.core.security import get_current_user
from app.core.exceptions import EntityNotFound
from app.services.audit import log_action

bp = Blueprint('eligibility', __name__)


@bp.route('/check', methods=['POST'])
def check_eligibility():
    """Run an eligibility check for a patient against a payer."""
    data = request.get_json()
    payload = EligibilityCheckRequest(**data)
    db = SessionLocal()
    try:
        user = get_current_user(db)
        patient_result = db.execute(select(Patient).where(Patient.id == payload.patient_id))
        patient = patient_result.scalar_one_or_none()
        if not patient:
            raise EntityNotFound('Patient', str(payload.patient_id))

        check = EligibilityCheck(
            patient_id=payload.patient_id,
            payer_id=payload.payer_id,
            checked_cpt_code=payload.cpt_code,
            subscriber_id=payload.subscriber_id,
            checked_by=user.email,
        )

        try:
            from app.services.fhir import fhir_client
            fhir_response = fhir_client.check_eligibility(
                patient_id=str(patient.fhir_patient_id or patient.id),
                payer_id=payload.payer_id,
                cpt_code=payload.cpt_code,
            )
            check.fhir_response = fhir_response
            check.status = EligibilityStatus.ACTIVE
            check.is_active = True
            check.plan_name = fhir_response.get('plan_name', 'Standard Plan')
            check.group_number = fhir_response.get('group_number')
            check.pa_required_for_cpt = fhir_response.get('pa_required', True)
            check.in_network = fhir_response.get('in_network')
        except Exception as exc:
            check.status = EligibilityStatus.ERROR
            check.error_message = str(exc)[:2000]

        db.add(check)
        db.flush()

        log_action(
            db,
            entity_type='eligibility_check',
            entity_id=check.id,
            action='eligibility_checked',
            actor=user.email,
            details={'payer_id': payload.payer_id, 'status': check.status.value},
        )

        db.commit()
        db.refresh(check)
        return jsonify(EligibilityCheckResponse.model_validate(check, from_attributes=True).model_dump(mode='json')), 201
    finally:
        db.close()


@bp.route('/', methods=['GET'])
def list_eligibility_checks():
    db = SessionLocal()
    try:
        user = get_current_user(db)
        patient_id = request.args.get('patient_id')
        payer_id = request.args.get('payer_id')
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 50, type=int)
        query = select(EligibilityCheck)
        if patient_id:
            query = query.where(EligibilityCheck.patient_id == str(patient_id))
        if payer_id:
            query = query.where(EligibilityCheck.payer_id == payer_id)
        query = query.order_by(EligibilityCheck.checked_at.desc()).offset(skip).limit(limit)
        result = db.execute(query)
        items = list(result.scalars().all())
        return jsonify([EligibilityCheckResponse.model_validate(i, from_attributes=True).model_dump(mode='json') for i in items])
    finally:
        db.close()


@bp.route('/<check_id>', methods=['GET'])
def get_eligibility_check(check_id):
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(EligibilityCheck).where(EligibilityCheck.id == str(check_id)))
        check = result.scalar_one_or_none()
        if not check:
            raise EntityNotFound('EligibilityCheck', check_id)
        return jsonify(EligibilityCheckResponse.model_validate(check, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()
