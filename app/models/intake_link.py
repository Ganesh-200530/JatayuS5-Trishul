from __future__ import annotations

import enum
import uuid
import secrets
from datetime import datetime

from sqlalchemy import String, DateTime, Enum, ForeignKey, func, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IntakeLinkStatus(str, enum.Enum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"


class PatientIntakeLink(Base):
    __tablename__ = "patient_intake_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False, default=lambda: secrets.token_urlsafe(48))
    status: Mapped[IntakeLinkStatus] = mapped_column(Enum(IntakeLinkStatus), default=IntakeLinkStatus.ACTIVE)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Optional: links to an existing PA for additional document requests
    prior_auth_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("prior_auth_requests.id"), nullable=True)
    missing_documents: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship()  # noqa: F821
