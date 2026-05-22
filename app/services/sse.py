"""Server-Sent Events (SSE) for real-time pipeline progress."""

from __future__ import annotations

import json
import queue
import threading
from typing import Generator

# Per-PA event queues: pa_id -> list of subscriber queues
_subscribers: dict[str, list[queue.Queue]] = {}
_lock = threading.Lock()


def subscribe(pa_id: str) -> queue.Queue:
    """Create a new SSE subscriber for a PA."""
    q: queue.Queue = queue.Queue()
    with _lock:
        _subscribers.setdefault(pa_id, []).append(q)
    return q


def unsubscribe(pa_id: str, q: queue.Queue) -> None:
    """Remove a subscriber."""
    with _lock:
        subs = _subscribers.get(pa_id, [])
        if q in subs:
            subs.remove(q)
        if not subs:
            _subscribers.pop(pa_id, None)


def emit(pa_id: str, event: str, data: dict) -> None:
    """Broadcast an event to all subscribers of a PA."""
    with _lock:
        subs = list(_subscribers.get(pa_id, []))
    payload = json.dumps(data)
    for q in subs:
        try:
            q.put_nowait((event, payload))
        except queue.Full:
            pass


def stream(pa_id: str) -> Generator[str, None, None]:
    """SSE generator for Flask response streaming."""
    q = subscribe(pa_id)
    try:
        # Send initial keepalive
        yield f": connected to {pa_id}\n\n"
        while True:
            try:
                event, payload = q.get(timeout=30)
                yield f"event: {event}\ndata: {payload}\n\n"
                if event == 'pipeline_complete':
                    break
            except queue.Empty:
                # Keepalive
                yield ": keepalive\n\n"
    finally:
        unsubscribe(pa_id, q)
