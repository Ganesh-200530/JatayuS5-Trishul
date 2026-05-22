from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EligibilityCheckRequest(BaseModel):
    patient_id: UUID
    payer_id: str = Field(..., max_length=50)
    cpt_code: str | None = Field(None, max_length=20)
    subscriber_id: str | None = Field(None, max_length=100)


class EligibilityCheckResponse(BaseModel):
    id: UUID
    patient_id: UUID
    payer_id: str
    status: str
    is_active: bool
    plan_name: str | None = None
    group_number: str | None = None
    subscriber_id: str | None = None
    coverage_start: datetime | None = None
    coverage_end: datetime | None = None
    pa_required_for_cpt: bool | None = None
    checked_cpt_code: str | None = None
    copay_amount: str | None = None
    coinsurance_pct: str | None = None
    deductible_remaining: str | None = None
    out_of_pocket_remaining: str | None = None
    in_network: bool | None = None
    error_message: str | None = None
    checked_at: datetime

    model_config = {"from_attributes": True}
