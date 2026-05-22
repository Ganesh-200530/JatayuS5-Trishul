from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.prior_auth import PAStatus, Urgency


class PriorAuthCreate(BaseModel):
    patient_id: uuid.UUID
    cpt_code: str = Field(..., max_length=20)
    cpt_description: str | None = None
    icd10_codes: list[str] = Field(default_factory=list)
    ordering_provider_npi: str | None = Field(None, max_length=20)
    ordering_provider_name: str | None = None
    facility_npi: str | None = None
    facility_name: str | None = None
    payer_id: str = Field(..., max_length=50)
    payer_name: str | None = None
    urgency: Urgency = Urgency.STANDARD
    clinical_notes: str | None = None  # optional raw notes to seed clinical reader


class PriorAuthUpdate(BaseModel):
    status: PAStatus | None = None
    requires_human_review: bool | None = None
    human_review_reason: str | None = None
    decision_reason: str | None = None


class PriorAuthRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: PAStatus
    urgency: Urgency
    cpt_code: str
    cpt_description: str | None
    icd10_codes: list[str]
    ordering_provider_npi: str
    ordering_provider_name: str | None
    facility_npi: str | None
    facility_name: str | None
    payer_id: str
    payer_name: str | None
    confidence_score: float | None
    requires_human_review: bool
    human_review_reason: str | None
    payer_tracking_number: str | None
    decision_reason: str | None
    decision_date: datetime | None
    metadata_: dict | None = Field(None, alias='metadata_')
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class PriorAuthListRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    status: PAStatus
    urgency: Urgency
    cpt_code: str
    payer_id: str
    confidence_score: float | None
    requires_human_review: bool
    created_at: datetime

    model_config = {"from_attributes": True}
