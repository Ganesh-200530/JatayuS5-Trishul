from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, Enum, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SubmissionChannel(str, enum.Enum):
    FHIR_PAS = "fhir_pas"
    X12_278 = "x12_278"
    PORTAL = "portal"
    FAX = "fax"


class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prior_auth_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("prior_auth_requests.id"), nullable=False
    )
    channel: Mapped[SubmissionChannel] = mapped_column(Enum(SubmissionChannel), nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(Enum(SubmissionStatus), default=SubmissionStatus.PENDING)

    # Payload
    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{name, content_type, fhir_ref}]

    # Tracking
    payer_tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prior_auth_request: Mapped["PriorAuthRequest"] = relationship(back_populates="submissions")  # noqa: F821
