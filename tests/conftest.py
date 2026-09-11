"""Pytest-wide configuration & dependency override for the BuildSure test suite.

All data-layer tests need a running database and a valid authentication context.
Rather than forcing every existing test file to add an ``Authorization`` header,
conftest replaces the ``get_current_manager`` dependency with a thin shim that
returns the seeded demo manager automatically. Auth-specific tests clear the
override locally so the real flow is exercised end-to-end.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ["TESTING"] = "1"
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-secret-key-at-least-32-bytes-long!!")
os.environ.setdefault("DEFAULT_MANAGER_PASSWORD", "test-pw")
os.environ.setdefault("DEFAULT_MANAGER_EMAIL", "manager@buildsure.io")

from sqlalchemy.orm import Session  # noqa: E402

from app.main import app  # noqa: E402
from app.database.database import SessionLocal, get_db  # noqa: E402
from app.auth.deps import get_current_manager  # noqa: E402
from app.models.models import Manager  # noqa: E402


def _test_manager() -> Manager:  # type: ignore[override]
    """Return the seeded demo manager without touching the request's DB session."""
    db: Session = SessionLocal()
    try:
        return db.query(Manager).filter(Manager.email == os.environ.get("DEFAULT_MANAGER_EMAIL", "manager@buildsure.io")).one()
    finally:
        db.close()


# Applied at module-collection time — before any test file imports app.
app.dependency_overrides[get_current_manager] = _test_manager