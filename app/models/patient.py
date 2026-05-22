from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mrn: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    payer_id: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payer_name: Mapped[str] = mapped_column(String(200), nullable=True)
    plan_id: Mapped[str] = mapped_column(String(50), nullable=True)
    subscriber_id: Mapped[str] = mapped_column(String(100), nullable=True)
    fhir_patient_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    prior_auth_requests: Mapped[list["PriorAuthRequest"]] = relationship(back_populates="patient")  # noqa: F821
