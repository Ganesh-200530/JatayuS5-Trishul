from __future__ import annotations

"""Eligibility check models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, Enum, ForeignKey, Boolean, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EligibilityStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class EligibilityCheck(Base):
    __tablename__ = "eligibility_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), nullable=False)
    payer_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[EligibilityStatus] = mapped_column(Enum(EligibilityStatus), default=EligibilityStatus.PENDING)

    # Coverage details
    plan_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    group_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subscriber_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    coverage_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    coverage_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    # PA requirements
    pa_required_for_cpt: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    checked_cpt_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Benefits
    copay_amount: Mapped[str | None] = mapped_column(String(20), nullable=True)
    coinsurance_pct: Mapped[str | None] = mapped_column(String(10), nullable=True)
    deductible_remaining: Mapped[str | None] = mapped_column(String(20), nullable=True)
    out_of_pocket_remaining: Mapped[str | None] = mapped_column(String(20), nullable=True)
    in_network: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Raw response
    fhir_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    checked_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
