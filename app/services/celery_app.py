from __future__ import annotations

"""Celery task queue with Redis broker. Falls back to FastAPI BackgroundTasks if unavailable."""

import structlog
from app.config import get_settings

logger = structlog.get_logger()

_celery_app = None
_celery_available = False


def get_celery_app():
    global _celery_app, _celery_available
    if _celery_app is not None:
        return _celery_app if _celery_available else None
    try:
        from celery import Celery
        settings = get_settings()
        _celery_app = Celery(
            "autoauth",
            broker=settings.CELERY_BROKER_URL,
            backend=settings.CELERY_RESULT_BACKEND,
        )
        _celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
            task_track_started=True,
            task_acks_late=True,
            worker_prefetch_multiplier=1,
            task_soft_time_limit=600,
            task_time_limit=900,
            task_default_retry_delay=30,
            task_max_retries=3,
        )
        # Test connectivity
        _celery_app.connection_for_write().ensure_connection(max_retries=1, timeout=2)
        _celery_available = True
        logger.info("celery.connected", broker=settings.CELERY_BROKER_URL)
    except Exception as exc:
        _celery_available = False
        logger.warning("celery.unavailable_using_background_tasks", error=str(exc))
    return _celery_app if _celery_available else None


def is_celery_available() -> bool:
    get_celery_app()
    return _celery_available
