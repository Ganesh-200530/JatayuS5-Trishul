from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PatientCreate(BaseModel):
    mrn: str | None = Field(None, max_length=50)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    date_of_birth: datetime
    gender: str = Field(..., max_length=20)
    email: str | None = None
    phone: str | None = None
    payer_id: str = Field(..., max_length=50)
    payer_name: str | None = None
    plan_id: str | None = None
    subscriber_id: str | None = None
    fhir_patient_id: str | None = None


class PatientUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    payer_id: str | None = None
    payer_name: str | None = None
    plan_id: str | None = None
    subscriber_id: str | None = None
    fhir_patient_id: str | None = None


class PatientRead(BaseModel):
    id: uuid.UUID
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: datetime
    gender: str
    email: str | None
    phone: str | None
    payer_id: str
    payer_name: str | None
    plan_id: str | None
    subscriber_id: str | None
    fhir_patient_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
