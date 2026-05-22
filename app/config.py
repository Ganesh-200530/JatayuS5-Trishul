from __future__ import annotations

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///medix.db"

    # ── Gemini ─────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # ── JWT Auth ───────────────────────────────────────────
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── FHIR ───────────────────────────────────────────────
    FHIR_BASE_URL: str = "http://localhost:8080/fhir"
    FHIR_AUTH_TOKEN: str = ""

    # ── Redis / Celery ─────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── PHI Encryption ─────────────────────────────────────
    PHI_ENCRYPTION_KEY: str = ""  # Fernet key; auto-generated if empty

    # ── Rate Limiting ──────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_AUTH: str = "10/minute"

    # ── Vector Store / RAG ─────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ── Medical NLP ────────────────────────────────────────
    SPACY_MODEL: str = "en_core_web_sm"

    # ── Portal RPA ─────────────────────────────────────────
    RPA_HEADLESS: bool = True
    RPA_TIMEOUT_MS: int = 30000

    # ── Notifications (Email / SMS) ────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = "noreply@medix.health"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # ── App ────────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CONFIDENCE_THRESHOLD: float = 0.70

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
