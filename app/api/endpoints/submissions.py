from __future__ import annotations

"""Submission tracking endpoints."""

import uuid

from flask import Blueprint, request, jsonify
from sqlalchemy import select

from app.database import SessionLocal
from app.models.submission import Submission
from app.core.security import get_current_user
from app.core.exceptions import EntityNotFound

bp = Blueprint('submissions', __name__)


@bp.route('/', methods=['GET'])
def list_submissions():
    db = SessionLocal()
    try:
        user = get_current_user(db)
        prior_auth_id = request.args.get('prior_auth_id')
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 50, type=int)
        query = select(Submission)
        if prior_auth_id:
            query = query.where(Submission.prior_auth_id == str(prior_auth_id))
        query = query.order_by(Submission.created_at.desc()).offset(skip).limit(limit)
        result = db.execute(query)
        subs = result.scalars().all()
        return jsonify([
            {
                'id': str(s.id),
                'prior_auth_id': str(s.prior_auth_id),
                'channel': s.channel.value,
                'status': s.status.value,
                'payer_tracking_number': s.payer_tracking_number,
                'submitted_at': s.submitted_at.isoformat() if s.submitted_at else None,
                'error_message': s.error_message,
                'created_at': s.created_at.isoformat() if s.created_at else None,
            }
            for s in subs
        ])
    finally:
        db.close()


@bp.route('/<submission_id>', methods=['GET'])
def get_submission(submission_id):
    db = SessionLocal()
    try:
        user = get_current_user(db)
        result = db.execute(select(Submission).where(Submission.id == str(submission_id)))
        sub = result.scalar_one_or_none()
        if not sub:
            raise EntityNotFound('Submission', submission_id)
        return jsonify({
            'id': str(sub.id),
            'prior_auth_id': str(sub.prior_auth_id),
            'channel': sub.channel.value,
            'status': sub.status.value,
            'payer_tracking_number': sub.payer_tracking_number,
            'submitted_at': sub.submitted_at.isoformat() if sub.submitted_at else None,
            'request_payload': sub.request_payload,
            'response_payload': sub.response_payload,
            'attachments': sub.attachments,
            'error_message': sub.error_message,
            'created_at': sub.created_at.isoformat() if sub.created_at else None,
        })
    finally:
        db.close()
