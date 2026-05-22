from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PayerCreate(BaseModel):
    payer_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=200)
    npi: str | None = Field(None, max_length=20)
    tax_id: str | None = Field(None, max_length=20)
    supports_fhir_pas: bool = False
    supports_x12_278: bool = False
    supports_portal: bool = False
    preferred_channel: str = Field("portal", max_length=20)
    fhir_endpoint: str | None = None
    x12_endpoint: str | None = None
    portal_url: str | None = None
    phone: str | None = Field(None, max_length=30)
    pa_phone: str | None = Field(None, max_length=30)
    pa_fax: str | None = Field(None, max_length=30)
    avg_response_hours: int | None = None
    auto_approve_enabled: bool = False


class PayerUpdate(BaseModel):
    name: str | None = None
    npi: str | None = None
    supports_fhir_pas: bool | None = None
    supports_x12_278: bool | None = None
    supports_portal: bool | None = None
    preferred_channel: str | None = None
    fhir_endpoint: str | None = None
    x12_endpoint: str | None = None
    portal_url: str | None = None
    phone: str | None = None
    pa_phone: str | None = None
    pa_fax: str | None = None
    avg_response_hours: int | None = None
    auto_approve_enabled: bool | None = None
    is_active: bool | None = None


class PayerResponse(BaseModel):
    id: UUID
    payer_id: str
    name: str
    npi: str | None = None
    tax_id: str | None = None
    supports_fhir_pas: bool
    supports_x12_278: bool
    supports_portal: bool
    preferred_channel: str
    fhir_endpoint: str | None = None
    x12_endpoint: str | None = None
    portal_url: str | None = None
    phone: str | None = None
    pa_phone: str | None = None
    pa_fax: str | None = None
    avg_response_hours: int | None = None
    auto_approve_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PayerListResponse(BaseModel):
    items: list[PayerResponse]
    total: int
