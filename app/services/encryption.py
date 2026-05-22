from __future__ import annotations

"""PHI field-level encryption for data at rest using Fernet symmetric encryption."""

import base64
import os
import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = structlog.get_logger()

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    settings = get_settings()
    key = settings.PHI_ENCRYPTION_KEY

    if not key:
        # Auto-generate and warn (dev mode only)
        key = Fernet.generate_key().decode()
        logger.warning(
            "encryption.auto_generated_key",
            hint="Set PHI_ENCRYPTION_KEY in .env for production",
        )

    # Ensure valid Fernet key (32 url-safe base64 bytes)
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        # If key is a passphrase, derive a Fernet key from it
        import hashlib
        derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        _fernet = Fernet(derived)

    return _fernet


def encrypt_phi(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns base64-encoded ciphertext."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_phi(ciphertext: str) -> str:
    """Decrypt a ciphertext string. Returns plaintext."""
    if not ciphertext:
        return ciphertext
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("encryption.decrypt_failed", hint="Key may have changed or data corrupted")
        return "[DECRYPTION_FAILED]"


def encrypt_dict_fields(data: dict, fields: list[str]) -> dict:
    """Encrypt specified fields in a dictionary."""
    result = data.copy()
    for field in fields:
        if field in result and result[field]:
            if isinstance(result[field], str):
                result[field] = encrypt_phi(result[field])
    return result


def decrypt_dict_fields(data: dict, fields: list[str]) -> dict:
    """Decrypt specified fields in a dictionary."""
    result = data.copy()
    for field in fields:
        if field in result and result[field]:
            if isinstance(result[field], str):
                result[field] = decrypt_phi(result[field])
    return result


# PHI fields that should be encrypted at rest
PHI_FIELDS = [
    "diagnosis_summary",
    "medical_necessity_justification",
    "raw_notes_text",
    "appeal_letter",
]
