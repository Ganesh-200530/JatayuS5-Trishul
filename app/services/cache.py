from __future__ import annotations

"""Redis cache with in-memory fallback when Redis is unavailable."""

import json
import time
import structlog
from typing import Any

from app.config import get_settings

logger = structlog.get_logger()

_redis_client = None
_redis_available = False
_redis_checked = False  # Ensure we only try once
_memory_cache: dict[str, tuple[Any, float]] = {}  # key -> (value, expiry_timestamp)


def _get_redis():
    global _redis_client, _redis_available, _redis_checked
    if _redis_checked:
        return _redis_client if _redis_available else None
    _redis_checked = True
    try:
        import redis
        settings = get_settings()
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        _redis_client.ping()
        _redis_available = True
        logger.info("cache.redis_connected", url=settings.REDIS_URL)
        return _redis_client
    except Exception as exc:
        _redis_available = False
        logger.warning("cache.redis_unavailable_using_memory", error=str(exc))
        return None


def cache_get(key: str) -> Any | None:
    """Get a value from cache. Returns None if not found or expired."""
    r = _get_redis()
    if r:
        try:
            val = r.get(key)
            return json.loads(val) if val else None
        except Exception:
            pass

    # Fallback to memory
    if key in _memory_cache:
        value, expiry = _memory_cache[key]
        if expiry > time.time():
            return value
        del _memory_cache[key]
    return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Set a value in cache with TTL."""
    r = _get_redis()
    if r:
        try:
            r.setex(key, ttl_seconds, json.dumps(value, default=str))
            return
        except Exception:
            pass

    # Fallback to memory
    _memory_cache[key] = (value, time.time() + ttl_seconds)


def cache_delete(key: str) -> None:
    """Delete a key from cache."""
    r = _get_redis()
    if r:
        try:
            r.delete(key)
        except Exception:
            pass
    _memory_cache.pop(key, None)


def cache_clear_prefix(prefix: str) -> None:
    """Delete all keys matching a prefix."""
    r = _get_redis()
    if r:
        try:
            for k in r.scan_iter(f"{prefix}*"):
                r.delete(k)
            return
        except Exception:
            pass

    keys_to_delete = [k for k in _memory_cache if k.startswith(prefix)]
    for k in keys_to_delete:
        del _memory_cache[k]


def is_redis_available() -> bool:
    _get_redis()
    return _redis_available
