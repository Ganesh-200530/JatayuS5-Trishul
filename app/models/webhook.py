from __future__ import annotations

"""Webhook event models for payer notifications."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, Enum, Boolean, Integer, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WebhookEventType(str, enum.Enum):
    PA_DECISION = "pa_decision"
    PA_STATUS_CHANGE = "pa_status_change"
    ELIGIBILITY_UPDATE = "eligibility_update"
    CLAIM_STATUS = "claim_status"
    DOCUMENT_REQUEST = "document_request"
    OTHER = "other"


class WebhookProcessingStatus(str, enum.Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_payer: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_type: Mapped[WebhookEventType] = mapped_column(Enum(WebhookEventType), default=WebhookEventType.OTHER)
    processing_status: Mapped[WebhookProcessingStatus] = mapped_column(
        Enum(WebhookProcessingStatus), default=WebhookProcessingStatus.RECEIVED
    )

    # Reference to PA
    pa_tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    pa_request_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # Event data
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parsed_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Processing
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Security
    signature_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
