from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ClinicalEvidenceCreate(BaseModel):
    prior_auth_id: uuid.UUID
    diagnosis_summary: str | None = None
    medical_necessity_justification: str | None = None
    treatment_history: list[dict] | None = None
    failed_conservative_therapies: list[str] | None = None
    supporting_findings: list[dict] | None = None
    relevant_lab_results: list[dict] | None = None
    relevant_imaging: list[dict] | None = None
    medications: list[dict] | None = None
    source_documents: list[dict] | None = None
    confidence_score: float | None = None


class ClinicalEvidenceRead(BaseModel):
    id: uuid.UUID
    prior_auth_id: uuid.UUID
    diagnosis_summary: str | None
    medical_necessity_justification: str | None
    treatment_history: list[dict] | None
    failed_conservative_therapies: list[str] | None
    supporting_findings: list[dict] | None
    relevant_lab_results: list[dict] | None
    relevant_imaging: list[dict] | None
    medications: list[dict] | None
    source_documents: list[dict] | None
    confidence_score: float | None
    extraction_model: str | None
    extraction_duration_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
