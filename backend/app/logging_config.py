"""Structured logging for the BuildSure platform (Milestone 4).

Keeps the console output greppable ``key=value`` style and guarantees secrets
are never written to logs. ``setup_logging()`` is intentionally sibling to the
existing uvicorn logging: it only configures the root logger level/format.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

from app.config import APP_ENV, LOG_LEVEL

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

_configured = False


def setup_logging() -> None:
    """Idempotent root-logger configuration. Safe to call more than once."""
    global _configured
    if _configured:
        return
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    _configured = True


def log_op(
    logger: logging.Logger,
    operation: str,
    *,
    status: str = "ok",
    site_id: Optional[str] = None,
    analysis_id: Optional[str] = None,
    error: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    """Emit a structured, single-line operation log entry.

    Never include credentials, tokens or passphrases in ``extra``.
    """
    parts = [f"op={operation}", f"status={status}"]
    if site_id:
        parts.append(f"site={site_id}")
    if analysis_id:
        parts.append(f"analysis={analysis_id}")
    if error:
        parts.append(f"error={error}")
    if extra:
        for key, value in sorted((extra or {}).items()):
            parts.append(f"{key}={value}")
    logger.info(" ".join(parts))