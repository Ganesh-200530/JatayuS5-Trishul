from __future__ import annotations

"""Audit logging service — immutable record of every action on PHI."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log_action(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor: str,
    details: dict | None = None,
    ip_address: str | None = None,
    previous_state: str | None = None,
    new_state: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        details=details,
        ip_address=ip_address,
        previous_state=previous_state,
        new_state=new_state,
    )
    db.add(entry)
    db.flush()
    return entry
