from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.appeal import AppealStatus, DenialReason


class AppealCreate(BaseModel):
    prior_auth_id: uuid.UUID
    denial_reason: DenialReason
    denial_details: str | None = None
    denial_code: str | None = None


class AppealRead(BaseModel):
    id: uuid.UUID
    prior_auth_id: uuid.UUID
    attempt_number: int
    status: AppealStatus
    denial_reason: DenialReason | None
    denial_details: str | None
    appeal_letter: str | None
    additional_evidence: list[dict] | None
    cited_references: list[dict] | None
    submitted_at: datetime | None
    response_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
