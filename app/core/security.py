from __future__ import annotations

"""Authentication & authorization utilities — JWT, refresh tokens, TOTP 2FA."""

import uuid
import secrets
import hashlib
import functools
import time as _time
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
import bcrypt as _bcrypt
from flask import request as flask_request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.core.exceptions import Unauthorized, Forbidden


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt(rounds=4)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT access token ──────────────────────────────────────


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    settings = get_settings()
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return TokenPayload(sub=str(data["sub"]), role=data["role"])
    except (JWTError, KeyError, ValueError) as exc:
        raise Unauthorized("Invalid or expired token") from exc


# ── Refresh token ─────────────────────────────────────────


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── TOTP 2FA ──────────────────────────────────────────────


def generate_totp_secret() -> str:
    try:
        import pyotp
        return pyotp.random_base32()
    except ImportError:
        return secrets.token_hex(20)


def verify_totp(secret: str, code: str) -> bool:
    try:
        import pyotp
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except ImportError:
        return False


def get_totp_provisioning_uri(secret: str, email: str) -> str:
    try:
        import pyotp
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name="AutoAuthAgent")
    except ImportError:
        return ""


# ── Auth helpers ──────────────────────────────────────────

_user_cache: dict[str, tuple[User, float]] = {}
_USER_CACHE_TTL = 30


def _extract_bearer_token() -> str:
    """Extract bearer token from the Authorization header."""
    auth = flask_request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise Unauthorized("Missing or invalid Authorization header")
    return auth[7:]


def get_current_user(db: Session) -> User:
    """Get the current authenticated user from the JWT token."""
    token = _extract_bearer_token()
    payload = decode_token(token)
    uid = str(payload.sub)
    now = _time.time()

    if uid in _user_cache:
        user, expiry = _user_cache[uid]
        if expiry > now and user.is_active:
            return user
        del _user_cache[uid]

    result = db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise Unauthorized("User not found or inactive")

    _user_cache[uid] = (user, now + _USER_CACHE_TTL)
    return user


def get_current_user_cached() -> User:
    """Lightweight auth — JWT + in-memory cache, DB fallback."""
    token = _extract_bearer_token()
    payload = decode_token(token)
    uid = str(payload.sub)
    now = _time.time()

    if uid in _user_cache:
        user, expiry = _user_cache[uid]
        if expiry > now and user.is_active:
            return user
        del _user_cache[uid]

    from app.database import SessionLocal
    db = SessionLocal()
    try:
        result = db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise Unauthorized("User not found or inactive")
        _user_cache[uid] = (user, now + _USER_CACHE_TTL)
        return user
    finally:
        db.close()


def require_role(*roles: str):
    """Decorator factory that checks the current user has one of the specified roles."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                user = get_current_user(db)
                if user.role not in roles:
                    raise Forbidden(f"Role '{user.role}' is not authorized. Required: {', '.join(roles)}")
            finally:
                db.close()
            return f(*args, **kwargs)
        return wrapper
    return decorator
