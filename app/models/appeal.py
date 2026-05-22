from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, Integer, Enum, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AppealStatus(str, enum.Enum):
    DRAFTING = "drafting"
    READY = "ready"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"


class DenialReason(str, enum.Enum):
    MISSING_INFO = "missing_information"
    MEDICAL_NECESSITY = "medical_necessity_not_met"
    OUT_OF_NETWORK = "out_of_network"
    CODING_ERROR = "coding_error"
    DUPLICATE = "duplicate"
    ADMINISTRATIVE = "administrative"
    OTHER = "other"


class Appeal(Base):
    __tablename__ = "appeals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prior_auth_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("prior_auth_requests.id"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[AppealStatus] = mapped_column(Enum(AppealStatus), default=AppealStatus.DRAFTING)

    # Denial context
    denial_reason: Mapped[DenialReason | None] = mapped_column(Enum(DenialReason), nullable=True)
    denial_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    denial_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Appeal content
    appeal_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cited_references: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Tracking
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    prior_auth_request: Mapped["PriorAuthRequest"] = relationship(back_populates="appeals")  # noqa: F821
