from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, Float, Enum, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PAStatus(str, enum.Enum):
    INITIATED = "initiated"
    CLINICAL_REVIEW = "clinical_review"
    POLICY_CHECK = "policy_check"
    SUBMISSION_READY = "submission_ready"
    SUBMITTED = "submitted"
    PENDING_DECISION = "pending_decision"
    APPROVED = "approved"
    DENIED = "denied"
    APPEAL_IN_PROGRESS = "appeal_in_progress"
    APPEAL_SUBMITTED = "appeal_submitted"
    APPEAL_APPROVED = "appeal_approved"
    APPEAL_DENIED = "appeal_denied"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"
    INTAKE_RECEIVED = "intake_received"


class Urgency(str, enum.Enum):
    STANDARD = "standard"
    URGENT = "urgent"
    EMERGENT = "emergent"


class PriorAuthRequest(Base):
    __tablename__ = "prior_auth_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), nullable=False)
    status: Mapped[PAStatus] = mapped_column(Enum(PAStatus), default=PAStatus.INITIATED, index=True)
    urgency: Mapped[Urgency] = mapped_column(Enum(Urgency), default=Urgency.STANDARD)

    # Order details
    cpt_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    cpt_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icd10_codes: Mapped[list] = mapped_column(JSON, default=list)
    ordering_provider_npi: Mapped[str] = mapped_column(String(20), nullable=False)
    ordering_provider_name: Mapped[str] = mapped_column(String(200), nullable=True)
    facility_npi: Mapped[str | None] = mapped_column(String(20), nullable=True)
    facility_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Payer
    payer_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Processing
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(default=False)
    human_review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tracking
    payer_tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="prior_auth_requests")  # noqa: F821
    clinical_evidence: Mapped["ClinicalEvidence | None"] = relationship(back_populates="prior_auth_request", uselist=False)  # noqa: F821
    submissions: Mapped[list["Submission"]] = relationship(back_populates="prior_auth_request")  # noqa: F821
    appeals: Mapped[list["Appeal"]] = relationship(back_populates="prior_auth_request")  # noqa: F821
