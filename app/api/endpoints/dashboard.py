from __future__ import annotations

"""Dashboard / analytics endpoints."""

import json
from flask import Blueprint, jsonify

from app.database import SessionLocal
from sqlalchemy import text

from app.core.security import get_current_user_cached
from app.services.cache import cache_get, cache_set

bp = Blueprint('dashboard', __name__)

_CACHE_KEY = 'dashboard:stats'
_CACHE_TTL = 10


@bp.route('/stats', methods=['GET'])
def get_dashboard_stats():
    """Return aggregate PA statistics -- SQLite-compatible queries."""
    user = get_current_user_cached()

    cached = cache_get(_CACHE_KEY)
    if cached is not None:
        return jsonify(cached)

    db = SessionLocal()
    try:
        # Status breakdown
        rows = db.execute(text(
            "SELECT status, count(*) AS cnt FROM prior_auth_requests GROUP BY status"
        )).fetchall()
        status_breakdown = {r.status: r.cnt for r in rows if r.cnt > 0}
        total = sum(r.cnt for r in rows)
        approved = sum(r.cnt for r in rows if r.status in ('approved', 'APPROVED', 'appeal_approved', 'APPEAL_APPROVED'))

        avg_conf = db.execute(text(
            "SELECT coalesce(avg(confidence_score), 0) AS v FROM prior_auth_requests WHERE confidence_score IS NOT NULL"
        )).scalar() or 0

        pending_review = db.execute(text(
            "SELECT count(*) FROM prior_auth_requests WHERE requires_human_review = 1"
        )).scalar() or 0

        total_appeals = db.execute(text(
            "SELECT count(*) FROM appeals"
        )).scalar() or 0

        appeal_wins = db.execute(text(
            "SELECT count(*) FROM appeals WHERE status = 'approved'"
        )).scalar() or 0
    finally:
        db.close()

    data = {
        'total_requests': total,
        'status_breakdown': status_breakdown,
        'approval_rate': round(approved / total, 3) if total > 0 else 0,
        'pending_human_review': int(pending_review),
        'average_confidence_score': round(float(avg_conf), 3) if avg_conf else 0,
        'total_appeals': total_appeals,
        'appeal_success_rate': round(appeal_wins / total_appeals, 3) if total_appeals > 0 else 0,
    }
    cache_set(_CACHE_KEY, data, _CACHE_TTL)
    return jsonify(data)


@bp.route('/analytics', methods=['GET'])
def get_analytics():
    """Get analytics data for charts."""
    db = SessionLocal()
    try:
        user = get_current_user_cached()
        from app.models.prior_auth import PriorAuthRequest, PAStatus
        from sqlalchemy import func, select

        # Approval rate by payer
        payer_stats = db.execute(
            select(
                PriorAuthRequest.payer_name,
                PriorAuthRequest.status,
                func.count(PriorAuthRequest.id)
            ).group_by(PriorAuthRequest.payer_name, PriorAuthRequest.status)
        ).all()

        payer_breakdown = {}
        for payer_name, status, count in payer_stats:
            name = payer_name or 'Unknown'
            if name not in payer_breakdown:
                payer_breakdown[name] = {'total': 0, 'approved': 0, 'denied': 0}
            payer_breakdown[name]['total'] += count
            if status == PAStatus.APPROVED or status == PAStatus.APPEAL_APPROVED:
                payer_breakdown[name]['approved'] += count
            elif status == PAStatus.DENIED or status == PAStatus.APPEAL_DENIED:
                payer_breakdown[name]['denied'] += count

        # Top denial reasons
        from app.models.appeal import Appeal
        denial_reasons = db.execute(
            select(Appeal.denial_reason, func.count(Appeal.id))
            .group_by(Appeal.denial_reason)
            .order_by(func.count(Appeal.id).desc())
            .limit(5)
        ).all()

        # Processing time stats (avg time from created to decision)
        decided = db.execute(
            select(PriorAuthRequest).where(
                PriorAuthRequest.decision_date.isnot(None)
            )
        ).scalars().all()

        avg_hours = 0
        if decided:
            total_hours = 0
            for pa in decided:
                if pa.created_at and pa.decision_date:
                    created = pa.created_at.replace(tzinfo=None) if pa.created_at.tzinfo else pa.created_at
                    decision = pa.decision_date.replace(tzinfo=None) if pa.decision_date.tzinfo else pa.decision_date
                    diff = (decision - created).total_seconds() / 3600
                    total_hours += diff
            avg_hours = round(total_hours / len(decided), 1) if decided else 0

        return jsonify({
            'payer_breakdown': [
                {'payer': k, 'total': v['total'], 'approved': v['approved'], 'denied': v['denied'],
                 'approval_rate': round(v['approved'] / v['total'], 2) if v['total'] > 0 else 0}
                for k, v in payer_breakdown.items()
            ],
            'top_denial_reasons': [
                {'reason': (r.value if r else 'unknown').replace('_', ' '), 'count': c}
                for r, c in denial_reasons
            ],
            'avg_processing_hours': avg_hours,
            'total_decided': len(decided),
        })
    finally:
        db.close()
