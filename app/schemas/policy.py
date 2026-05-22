from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PolicyCriterionCreate(BaseModel):
    criterion_code: str = Field(..., max_length=50)
    description: str
    criterion_type: str = Field(..., max_length=50)
    evaluation_logic: dict | None = None
    is_mandatory: bool = True


class PayerPolicyCreate(BaseModel):
    payer_id: str = Field(..., max_length=50)
    payer_name: str = Field(..., max_length=200)
    cpt_code: str = Field(..., max_length=20)
    cpt_description: str | None = None
    pa_required: bool = True
    policy_document_url: str | None = None
    policy_text: str | None = None
    effective_date: datetime | None = None
    expiration_date: datetime | None = None
    criteria: list[PolicyCriterionCreate] = Field(default_factory=list)


class PayerPolicyRead(BaseModel):
    id: uuid.UUID
    payer_id: str
    payer_name: str
    cpt_code: str
    cpt_description: str | None
    pa_required: bool
    policy_document_url: str | None
    effective_date: datetime | None
    expiration_date: datetime | None
    last_synced_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CriterionResult(BaseModel):
    criterion_code: str
    description: str
    is_met: bool
    evidence_citation: str | None = None
    confidence: float = 0.0


class PolicyGapAnalysis(BaseModel):
    prior_auth_id: uuid.UUID
    payer_id: str
    cpt_code: str
    pa_required: bool
    criteria_results: list[CriterionResult]
    all_mandatory_met: bool
    overall_confidence: float
    recommendation: str  # "approve", "deny", "needs_review"
    gap_summary: str | None = None
