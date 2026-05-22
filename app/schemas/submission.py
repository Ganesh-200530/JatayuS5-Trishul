from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.submission import SubmissionChannel, SubmissionStatus


class SubmissionRead(BaseModel):
    id: uuid.UUID
    prior_auth_id: uuid.UUID
    channel: SubmissionChannel
    status: SubmissionStatus
    payer_tracking_number: str | None
    error_message: str | None
    submitted_at: datetime | None
    response_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
