"""Milestone 4 — manager authentication & site authorization, end-to-end.

These tests clear the conftest dependency override so the REAL login/token
flow is exercised: hashed passwords, JWT issuance, token-version logout, and
server-side site authorization (a manager can only read their own site).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database.database import Base, engine, init_db, SessionLocal  # noqa: E402
from app.auth.deps import get_current_manager  # noqa: E402
from app.models.models import Manager  # noqa: E402

DEMO_EMAIL = "manager@buildsure.io"
DEMO_PASS = "test-pw"


@pytest.fixture
def client():
    """TestClient WITHOUT the conftest auth override (real auth path)."""
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.pop(get_current_manager, None)
    c = TestClient(app)
    yield c
    app.dependency_overrides = saved


@pytest.fixture(scope="module", autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    from app.services.seed import seed_demo_data
    seed_demo_data()
    yield


def _login(c, email=DEMO_EMAIL, password=DEMO_PASS):
    return c.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]


def test_login_success_and_me(client):
    r = client.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["manager"]["email"] == DEMO_EMAIL
    token = body["access_token"]

    r2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    me = r2.json()
    assert me["site_id"] == "site_riverside_main"
    # password_hash is NEVER exposed through the API.
    assert "password_hash" not in r2.text


def test_login_rejects_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": "wrong-pass"})
    assert r.status_code == 401


def test_login_rejects_unknown_user(client):
    r = client.post("/api/auth/login", json={"email": "nobody@buildsure.io", "password": DEMO_PASS})
    assert r.status_code == 401


def test_protected_route_requires_token(client):
    r = client.get("/api/sites/site_riverside_main/dashboard")
    assert r.status_code == 401


def test_inactive_manager_cannot_login(client):
    db = SessionLocal()
    try:
        m = db.query(Manager).filter(Manager.email == DEMO_EMAIL).first()
        m.is_active = 0
        db.commit()
    finally:
        db.close()
    r = client.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS})
    assert r.status_code == 401


def test_inactive_manager_token_rejected(client):
    # Re-activate, login, then deactivate -> the already-issued token must die.
    db = SessionLocal()
    try:
        m = db.query(Manager).filter(Manager.email == DEMO_EMAIL).first()
        m.is_active = 1
        db.commit()
    finally:
        db.close()
    token = _login(client)
    db = SessionLocal()
    try:
        m = db.query(Manager).filter(Manager.email == DEMO_EMAIL).first()
        m.is_active = 0
        db.commit()
    finally:
        db.close()
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    # Restore so later tests in this module are unaffected.
    db = SessionLocal()
    try:
        m = db.query(Manager).filter(Manager.email == DEMO_EMAIL).first()
        m.is_active = 1
        db.commit()
    finally:
        db.close()


def test_logout_invalidates_token(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    # Same token is now invalid because token_version was bumped.
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_site_authorization_enforced(client):
    """A manager scoped to site_riverside_main cannot read other sites."""
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Own site: allowed.
    assert client.get("/api/sites/site_riverside_main/dashboard", headers=headers).status_code == 200
    # Foreign site: 403.
    assert client.get("/api/sites/site_elsewhere/dashboard", headers=headers).status_code == 403
    # Foreign site via JSON body (monitoring/analyze): 403 before any write.
    assert client.post(
        "/api/monitoring/analyze",
        json={"site_id": "site_elsewhere", "event_type": "test", "source": "test"},
        headers=headers,
    ).status_code == 403
    # Foreign site via query param on a POST route: 403.
    assert client.post(
        "/api/monitoring/simulate", params={"site_id": "site_elsewhere"}, headers=headers
    ).status_code == 403


def test_password_hash_is_strong_scrypt():
    from app.auth.security import hash_password, verify_password
    h = hash_password("s3cret-value")
    assert h.startswith("scrypt$")
    assert verify_password("s3cret-value", h)
    assert not verify_password("nope", h)


def test_token_query_param_fallback_for_media(client):
    """Protected endpoints accept a ?token= query param (needed for media streams)."""
    token = _login(client)
    r = client.get(
        "/api/sites/site_riverside_main/live/status",
        params={"token": token},
    )
    assert r.status_code == 200
    # Without any token the same endpoint returns 401.
    r2 = client.get("/api/sites/site_riverside_main/live/status")
    assert r2.status_code == 401


def test_ws_get_manager_auths_query_token(client):
    """WebSocket handshakes authenticate via ?token= (headers don't apply to WS)."""
    from app.auth.deps import ws_get_manager
    from app.database.database import SessionLocal

    token = _login(client)
    db = SessionLocal()
    try:
        m = ws_get_manager(db, token)
        assert m is not None and m.email == DEMO_EMAIL
        assert ws_get_manager(db, "garbage-token") is None
        assert ws_get_manager(db, None) is None
    finally:
        db.close()