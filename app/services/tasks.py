from __future__ import annotations

"""Celery tasks -- durable wrappers around the PA pipeline and appeal process."""

import uuid
import structlog

logger = structlog.get_logger()


def run_pipeline_task(pa_id: str, clinical_notes: str | None = None) -> dict:
    """Celery task: run the full PA pipeline with retries and persistence."""
    from app.database import SessionLocal
    from app.models.prior_auth import PriorAuthRequest
    from app.agents.orchestrator import Orchestrator
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    db = SessionLocal()
    try:
        result = db.execute(
            select(PriorAuthRequest)
            .options(selectinload(PriorAuthRequest.patient))
            .where(PriorAuthRequest.id == uuid.UUID(pa_id))
        )
        pa = result.scalar_one_or_none()
        if not pa:
            return {'error': f'PA {pa_id} not found'}
        orchestrator = Orchestrator(db)
        return orchestrator.run_full_pipeline(pa, clinical_notes)
    finally:
        db.close()


def run_appeal_task(
    pa_id: str, denial_reason: str, denial_details: str, denial_code: str | None = None
) -> dict:
    """Celery task: handle a denial with appeals."""
    from app.database import SessionLocal
    from app.models.prior_auth import PriorAuthRequest
    from app.agents.orchestrator import Orchestrator
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    db = SessionLocal()
    try:
        result = db.execute(
            select(PriorAuthRequest)
            .options(selectinload(PriorAuthRequest.patient))
            .where(PriorAuthRequest.id == uuid.UUID(pa_id))
        )
        pa = result.scalar_one_or_none()
        if not pa:
            return {'error': f'PA {pa_id} not found'}
        orchestrator = Orchestrator(db)
        return orchestrator.handle_denial(pa, denial_reason, denial_details, denial_code)
    finally:
        db.close()


def check_eligibility_task(patient_id: str, payer_id: str) -> dict:
    """Celery task: run eligibility check."""
    from app.services.fhir import fhir_client
    return fhir_client.check_coverage_eligibility(patient_id, payer_id)


# Register tasks with Celery if available
def register_celery_tasks():
    """Register all tasks with the Celery app."""
    from app.services.celery_app import get_celery_app
    app = get_celery_app()
    if app:
        app.task(bind=True, name='autoauth.run_pipeline', max_retries=3)(
            lambda self, *a, **kw: run_pipeline_task(*a, **kw)
        )
        app.task(bind=True, name='autoauth.run_appeal', max_retries=3)(
            lambda self, *a, **kw: run_appeal_task(*a, **kw)
        )
        app.task(bind=True, name='autoauth.check_eligibility', max_retries=2)(
            lambda self, *a, **kw: check_eligibility_task(*a, **kw)
        )
        logger.info('celery.tasks_registered')
