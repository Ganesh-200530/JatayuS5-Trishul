from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WebhookEventResponse(BaseModel):
    id: UUID
    source_payer: str
    event_type: str
    processing_status: str
    pa_tracking_number: str | None = None
    pa_request_id: UUID | None = None
    decision: str | None = None
    reason: str | None = None
    retry_count: int
    error_message: str | None = None
    processed_at: datetime | None = None
    received_at: datetime

    model_config = {"from_attributes": True}


class WebhookIngestRequest(BaseModel):
    source: str = Field(..., max_length=100)
    event_type: str = Field("other", max_length=50)
    tracking_number: str | None = Field(None, max_length=100)
    payload: dict


class WebhookListResponse(BaseModel):
    items: list[WebhookEventResponse]
    total: int
