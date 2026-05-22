from __future__ import annotations

"""Audit log query endpoints."""

import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify
from sqlalchemy import select, func, and_

from app.database import SessionLocal
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse, AuditLogListResponse
from app.core.security import require_role

bp = Blueprint('audit_logs', __name__)


@bp.route('/', methods=['GET'])
@require_role('admin', 'reviewer')
def list_audit_logs():
    """Query audit logs with filters. Admin/reviewer only."""
    db = SessionLocal()
    try:
        entity_type = request.args.get('entity_type')
        entity_id = request.args.get('entity_id')
        action = request.args.get('action')
        actor = request.args.get('actor')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        conditions = []
        if entity_type:
            conditions.append(AuditLog.entity_type == entity_type)
        if entity_id:
            conditions.append(AuditLog.entity_id == str(entity_id))
        if action:
            conditions.append(AuditLog.action == action)
        if actor:
            conditions.append(AuditLog.actor == actor)
        if date_from:
            conditions.append(AuditLog.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            conditions.append(AuditLog.created_at <= datetime.fromisoformat(date_to))

        base_query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        if conditions:
            base_query = base_query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        total_result = db.execute(count_query)
        total = total_result.scalar()

        query = base_query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        result = db.execute(query)
        items = list(result.scalars().all())

        resp = AuditLogListResponse(items=items, total=total, limit=limit, offset=offset)
        return jsonify(resp.model_dump(mode='json'))
    finally:
        db.close()


@bp.route('/entity/<entity_type>/<entity_id>', methods=['GET'])
@require_role('admin', 'reviewer')
def get_entity_audit_trail(entity_type, entity_id):
    """Get complete audit trail for a specific entity."""
    db = SessionLocal()
    try:
        result = db.execute(
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == str(entity_id))
            .order_by(AuditLog.created_at.asc())
        )
        items = list(result.scalars().all())
        return jsonify([AuditLogResponse.model_validate(i, from_attributes=True).model_dump(mode='json') for i in items])
    finally:
        db.close()
