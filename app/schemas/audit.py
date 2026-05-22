from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogQuery(BaseModel):
    entity_type: str | None = None
    entity_id: UUID | None = None
    action: str | None = None
    actor: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class AuditLogResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    actor: str
    details: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int
