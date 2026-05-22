from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, Float, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ClinicalEvidence(Base):
    __tablename__ = "clinical_evidences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prior_auth_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("prior_auth_requests.id"), unique=True, nullable=False
    )

    # Extracted evidence
    diagnosis_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    medical_necessity_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    treatment_history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    failed_conservative_therapies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    supporting_findings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    relevant_lab_results: Mapped[list | None] = mapped_column(JSON, nullable=True)
    relevant_imaging: Mapped[list | None] = mapped_column(JSON, nullable=True)
    medications: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Source tracking
    source_documents: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{fhir_id, type, date, excerpt}]
    raw_notes_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Quality
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extraction_duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prior_auth_request: Mapped["PriorAuthRequest"] = relationship(back_populates="clinical_evidence")  # noqa: F821
