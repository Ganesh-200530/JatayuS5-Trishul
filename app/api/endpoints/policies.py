from __future__ import annotations

"""Payer Policy management endpoints."""

import uuid

from flask import Blueprint, request, jsonify
from sqlalchemy import select

from app.database import SessionLocal
from app.models.policy import PayerPolicy, PolicyCriterion
from app.schemas.policy import PayerPolicyCreate, PayerPolicyRead
from app.core.security import get_current_user, require_role
from app.core.exceptions import EntityNotFound

bp = Blueprint('policies', __name__)


@bp.route('/', methods=['POST'])
@require_role('admin')
def create_policy():
    data = request.get_json()
    payload = PayerPolicyCreate(**data)
    db = SessionLocal()
    try:
        policy = PayerPolicy(
            payer_id=payload.payer_id,
            payer_name=payload.payer_name,
            cpt_code=payload.cpt_code,
            cpt_description=payload.cpt_description,
            pa_required=payload.pa_required,
            policy_document_url=payload.policy_document_url,
            policy_text=payload.policy_text,
            effective_date=payload.effective_date,
            expiration_date=payload.expiration_date,
        )
        db.add(policy)
        db.flush()

        for criterion in payload.criteria:
            db.add(
                PolicyCriterion(
                    policy_id=policy.id,
                    criterion_code=criterion.criterion_code,
                    description=criterion.description,
                    criterion_type=criterion.criterion_type,
                    evaluation_logic=criterion.evaluation_logic,
                    is_mandatory=criterion.is_mandatory,
                )
            )

        db.commit()
        db.refresh(policy)
        return jsonify(PayerPolicyRead.model_validate(policy, from_attributes=True).model_dump(mode='json')), 201
    finally:
        db.close()


@bp.route('/', methods=['GET'])
def list_policies():
    db = SessionLocal()
    try:
        user = get_current_user(db)
        payer_id = request.args.get('payer_id')
        cpt_code = request.args.get('cpt_code')
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 50, type=int)
        query = select(PayerPolicy)
        if payer_id:
            query = query.where(PayerPolicy.payer_id == payer_id)
        if cpt_code:
            query = query.where(PayerPolicy.cpt_code == cpt_code)
        query = query.order_by(PayerPolicy.created_at.desc()).offset(skip).limit(limit)
        result = db.execute(query)
        items = list(result.scalars().all())
        return jsonify([PayerPolicyRead.model_validate(i, from_attributes=True).model_dump(mode='json') for i in items])
    finally:
        db.close()


@bp.route('/<policy_id>', methods=['GET'])
def get_policy(policy_id):
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(PayerPolicy).where(PayerPolicy.id == str(policy_id)))
        policy = result.scalar_one_or_none()
        if not policy:
            raise EntityNotFound('PayerPolicy', policy_id)
        return jsonify(PayerPolicyRead.model_validate(policy, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()
