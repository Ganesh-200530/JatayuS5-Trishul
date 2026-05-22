from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, Boolean, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PayerPolicy(Base):
    __tablename__ = "payer_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payer_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    cpt_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    cpt_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pa_required: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_document_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    policy_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PolicyCriterion(Base):
    __tablename__ = "policy_criteria"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("payer_policies.id"), nullable=False)
    criterion_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    criterion_type: Mapped[str] = mapped_column(String(50), nullable=False)  # required, preferred, exclusion
    evaluation_logic: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
