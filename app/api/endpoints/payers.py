from __future__ import annotations

"""Payer registry endpoints."""

import uuid

from flask import Blueprint, request, jsonify
from sqlalchemy import select, func

from app.database import SessionLocal
from app.models.payer import Payer
from app.schemas.payer import PayerCreate, PayerUpdate, PayerResponse, PayerListResponse
from app.core.security import get_current_user, require_role
from app.core.exceptions import EntityNotFound, DuplicateEntity

bp = Blueprint('payers', __name__)


@bp.route('/', methods=['POST'])
@require_role('admin')
def create_payer():
    data = request.get_json()
    payload = PayerCreate(**data)
    db = SessionLocal()
    try:
        existing = db.execute(select(Payer).where(Payer.payer_id == payload.payer_id))
        if existing.scalar_one_or_none():
            raise DuplicateEntity('Payer', 'payer_id', payload.payer_id)

        payer = Payer(**payload.model_dump())
        db.add(payer)
        db.commit()
        db.refresh(payer)
        return jsonify(PayerResponse.model_validate(payer, from_attributes=True).model_dump(mode='json')), 201
    finally:
        db.close()


@bp.route('/', methods=['GET'])
def list_payers():
    db = SessionLocal()
    try:
        user = get_current_user(db)
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 50, type=int)

        query = select(Payer)
        count_query = select(func.count(Payer.id))
        if active_only:
            query = query.where(Payer.is_active == True)
            count_query = count_query.where(Payer.is_active == True)

        total_result = db.execute(count_query)
        total = total_result.scalar()

        query = query.order_by(Payer.name).offset(skip).limit(limit)
        result = db.execute(query)
        items = list(result.scalars().all())

        resp = PayerListResponse(items=items, total=total)
        return jsonify(resp.model_dump(mode='json'))
    finally:
        db.close()


@bp.route('/<payer_db_id>', methods=['GET'])
def get_payer(payer_db_id):
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(Payer).where(Payer.id == str(payer_db_id)))
        payer = result.scalar_one_or_none()
        if not payer:
            raise EntityNotFound('Payer', payer_db_id)
        return jsonify(PayerResponse.model_validate(payer, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()


@bp.route('/<payer_db_id>', methods=['PATCH'])
@require_role('admin')
def update_payer(payer_db_id):
    data = request.get_json()
    payload = PayerUpdate(**data)
    db = SessionLocal()
    try:
        result = db.execute(select(Payer).where(Payer.id == str(payer_db_id)))
        payer = result.scalar_one_or_none()
        if not payer:
            raise EntityNotFound('Payer', payer_db_id)

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(payer, field, value)

        db.commit()
        db.refresh(payer)
        return jsonify(PayerResponse.model_validate(payer, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()
