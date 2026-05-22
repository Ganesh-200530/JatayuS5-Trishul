from __future__ import annotations

"""Webhook ingestion endpoints for payer notifications."""

import uuid
from datetime import datetime, timezone

import structlog
from flask import Blueprint, request as flask_request, jsonify
from sqlalchemy import select, func

from app.database import SessionLocal
from app.models.webhook import WebhookEvent, WebhookEventType, WebhookProcessingStatus
from app.models.prior_auth import PriorAuthRequest, PAStatus
from app.schemas.webhook import WebhookEventResponse, WebhookIngestRequest, WebhookListResponse
from app.core.security import get_current_user, require_role
from app.core.exceptions import EntityNotFound
from app.services.audit import log_action

logger = structlog.get_logger()

bp = Blueprint('webhooks', __name__)


@bp.route('/payer', methods=['POST'])
def ingest_payer_webhook():
    """Receive a payer webhook notification (PA decision, status change, etc.)."""
    data = flask_request.get_json()
    payload = WebhookIngestRequest(**data)
    db = SessionLocal()
    try:
        event_type_map = {
            'pa_decision': WebhookEventType.PA_DECISION,
            'pa_status_change': WebhookEventType.PA_STATUS_CHANGE,
            'eligibility_update': WebhookEventType.ELIGIBILITY_UPDATE,
            'claim_status': WebhookEventType.CLAIM_STATUS,
            'document_request': WebhookEventType.DOCUMENT_REQUEST,
        }
        event_type = event_type_map.get(payload.event_type, WebhookEventType.OTHER)

        event = WebhookEvent(
            source_payer=payload.source,
            event_type=event_type,
            pa_tracking_number=payload.tracking_number,
            raw_payload=payload.payload,
            source_ip=flask_request.remote_addr,
            processing_status=WebhookProcessingStatus.RECEIVED,
        )
        db.add(event)
        db.flush()

        try:
            event.processing_status = WebhookProcessingStatus.PROCESSING
            _process_webhook(db, event, payload.payload)
            event.processing_status = WebhookProcessingStatus.PROCESSED
            event.processed_at = datetime.now(timezone.utc)
        except Exception as exc:
            event.processing_status = WebhookProcessingStatus.FAILED
            event.error_message = str(exc)[:2000]
            logger.error('webhook.processing_failed', event_id=str(event.id), error=str(exc))

        db.commit()
        db.refresh(event)
        return jsonify(WebhookEventResponse.model_validate(event, from_attributes=True).model_dump(mode='json')), 201
    finally:
        db.close()


def _process_webhook(db, event, payload):
    """Process a webhook event -- update PA status if applicable."""
    decision = payload.get('decision')
    tracking = event.pa_tracking_number

    if not tracking:
        event.parsed_data = {'note': 'No tracking number, stored for reference'}
        return

    result = db.execute(
        select(PriorAuthRequest).where(PriorAuthRequest.payer_tracking_number == tracking)
    )
    pa = result.scalar_one_or_none()

    if pa:
        event.pa_request_id = pa.id
        event.decision = decision

        status_map = {
            'approved': PAStatus.APPROVED,
            'denied': PAStatus.DENIED,
            'pended': PAStatus.PENDING_DECISION,
            'cancelled': PAStatus.CANCELLED,
        }
        new_status = status_map.get(decision)
        if new_status:
            old_status = pa.status.value
            pa.status = new_status
            pa.decision_reason = payload.get('reason')

            log_action(
                db,
                entity_type='prior_auth_request',
                entity_id=pa.id,
                action='status_changed_via_webhook',
                actor=f'webhook:{event.source_payer}',
                previous_state=old_status,
                new_state=new_status.value,
                details={'webhook_event_id': str(event.id)},
            )

        event.parsed_data = {
            'pa_id': str(pa.id),
            'decision': decision,
            'previous_status': old_status if new_status else None,
            'new_status': new_status.value if new_status else None,
        }
    else:
        event.parsed_data = {'note': f'No PA found for tracking number {tracking}'}


@bp.route('/', methods=['GET'])
@require_role('admin', 'reviewer')
def list_webhooks():
    db = SessionLocal()
    try:
        source_payer = flask_request.args.get('source_payer')
        event_type = flask_request.args.get('event_type')
        processing_status = flask_request.args.get('processing_status')
        skip = flask_request.args.get('skip', 0, type=int)
        limit = flask_request.args.get('limit', 50, type=int)

        query = select(WebhookEvent)
        if source_payer:
            query = query.where(WebhookEvent.source_payer == source_payer)
        if event_type:
            query = query.where(WebhookEvent.event_type == event_type)
        if processing_status:
            query = query.where(WebhookEvent.processing_status == processing_status)

        count_result = db.execute(select(func.count(WebhookEvent.id)))
        total = count_result.scalar()

        query = query.order_by(WebhookEvent.received_at.desc()).offset(skip).limit(limit)
        result = db.execute(query)
        items = list(result.scalars().all())

        resp = WebhookListResponse(items=items, total=total)
        return jsonify(resp.model_dump(mode='json'))
    finally:
        db.close()


@bp.route('/<event_id>', methods=['GET'])
@require_role('admin', 'reviewer')
def get_webhook(event_id):
    db = SessionLocal()
    try:
        result = db.execute(select(WebhookEvent).where(WebhookEvent.id == str(event_id)))
        event = result.scalar_one_or_none()
        if not event:
            raise EntityNotFound('WebhookEvent', event_id)
        return jsonify(WebhookEventResponse.model_validate(event, from_attributes=True).model_dump(mode='json'))
    finally:
        db.close()
