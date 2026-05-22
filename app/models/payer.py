from __future__ import annotations

"""Payer Registry — master data for payer organizations."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Payer(Base):
    __tablename__ = "payers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payer_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    npi: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Submission capabilities
    supports_fhir_pas: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_x12_278: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_portal: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_channel: Mapped[str] = mapped_column(String(20), default="fhir_pas")  # fhir_pas, x12_278, portal

    # Endpoints
    fhir_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    x12_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portal_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Contact
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pa_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pa_fax: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Configuration
    avg_response_hours: Mapped[int | None] = mapped_column(nullable=True)
    auto_approve_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    portal_credentials_vault_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    extra_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
