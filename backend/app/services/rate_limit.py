"""In-process sliding-window rate limiter for authentication attempts.

Deliberately dependency-free (no Redis): fits the current single-process
FastAPI deployment. When the API is scaled out to multiple worker processes the
failure window is per-process; a shared store (Redis) becomes necessary then.
Only the number and timing of failures are tracked — passwords are never
stored or logged here.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, List

from app.config import LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS

_lock = threading.Lock()
_failures: Dict[str, List[float]] = {}


def _prune(key: str, now: float) -> List[float]:
    bucket = _failures.get(key, [])
    bucket = [t for t in bucket if t > now - LOGIN_WINDOW_SECONDS]
    _failures[key] = bucket
    return bucket


def record_failure(key: str) -> int:
    """Record a failed login attempt; returns the count in the current window."""
    now = time.monotonic()
    with _lock:
        _prune(key, now)
        _failures[key].append(now)
        return len(_failures[key])


def is_blocked(key: str) -> bool:
    """True when ``key`` may no longer attempt a login right now."""
    now = time.monotonic()
    with _lock:
        return len(_prune(key, now)) >= LOGIN_MAX_ATTEMPTS


def clear_failures(key: str) -> None:
    """Reset the window on a successful login for ``key``."""
    with _lock:
        _failures.pop(key, None)