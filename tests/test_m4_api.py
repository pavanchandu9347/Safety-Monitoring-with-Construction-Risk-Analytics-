"""Milestone 4 — Reporting Intelligence API, security & notifications.

Covers: report generate/list/latest/detail/text, the unified intelligence and
historical analytics endpoints, 404s for missing resources, backend-enforced
per-site authorization (manager A -> site B rejected), token requirements, and
the notification hook that must never break report generation.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

os.environ["TESTING"] = "1"
from app.main import app  # noqa: E402
from app.database.database import (  # noqa: E402
    Base, engine, init_db, SessionLocal,
)
from app.services.analysis_pipeline import run_analysis  # noqa: E402
from app.auth.deps import get_current_manager  # noqa: E402
from app.models.models import RiskReport, Manager  # noqa: E402

SITE_ID = "site_riverside_main"

client = TestClient(app)

DEMO_EMAIL = "manager@buildsure.io"
DEMO_PASS = "test-pw"


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    from app.services.seed import seed_demo_data
    seed_demo_data()
    yield


@pytest.fixture(scope="module")
def analysis_id():
    db = SessionLocal()
    try:
        result = run_analysis(db, site_id=SITE_ID)
    finally:
        db.close()
    assert result["status"] == "completed"
    return result["analysis_id"]


@pytest.fixture
def real_client():
    """TestClient WITHOUT the conftest auth override (real token flow)."""
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.pop(get_current_manager, None)
    c = TestClient(app)
    yield c
    app.dependency_overrides = saved


def _login(c, email=DEMO_EMAIL, password=DEMO_PASS):
    return c.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]


def test_generate_report_api(analysis_id):
    r = client.post(
        f"/api/sites/{SITE_ID}/reports/generate",
        json={"analysis_id": analysis_id, "report_type": "risk_intelligence"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["analysis_id"] == analysis_id
    assert body["site_id"] == SITE_ID
    assert body["status"] == "completed"
    content = body["content"]
    assert content["executive_summary"]["short_line"]
    assert content["historical_analytics"]["trend_available"] is False
    # 13-section structure is present and evidence-traceable.
    assert content["site_info"]["site_id"] == SITE_ID
    assert content["analysis_info"]["analysis_id"] == analysis_id
    assert isinstance(content["limitations"], list) and content["limitations"]
    assert {"risk", "safety", "compliance", "insurance"} <= set(content["sections"].keys())
    assert "site_risk" in content["sections"]["risk"]
    assert isinstance(content["evidence_summary"]["counts"], dict)
    # The notification hook runs but never fails the report.
    assert isinstance(body["notifications_raised"], list)


def test_notification_failure_never_fails_report(analysis_id, monkeypatch):
    """A raising notification subsystem must not turn a report into a 500."""

    def _boom(*args, **kwargs):
        raise RuntimeError("notification backend down")

    monkeypatch.setattr("app.api.reports.maybe_notify", _boom)
    r = client.post(
        f"/api/sites/{SITE_ID}/reports/generate",
        json={"analysis_id": analysis_id},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["notifications_raised"] == 0


def test_generate_report_defaults_to_latest_analysis(analysis_id):
    r = client.post(f"/api/sites/{SITE_ID}/reports/generate", json={})
    assert r.status_code == 200
    assert r.json()["analysis_id"] == analysis_id


def test_list_latest_and_detail_reports(analysis_id):
    created = client.post(
        f"/api/sites/{SITE_ID}/reports/generate",
        json={"analysis_id": analysis_id},
    ).json()
    assert created["id"]

    r = client.get(f"/api/sites/{SITE_ID}/reports")
    assert r.status_code == 200
    body = r.json()
    assert body["site_id"] == SITE_ID
    assert body["count"] >= 1
    report = next(
        (row for row in body["reports"] if row["id"] == created["id"]), None
    )
    assert report is not None
    assert report["analysis_id"] == analysis_id

    r = client.get(f"/api/sites/{SITE_ID}/reports/latest")
    assert r.status_code == 200
    assert r.json()["id"] == body["reports"][0]["id"]

    r = client.get(f"/api/sites/{SITE_ID}/reports/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]

    r = client.get(f"/api/sites/{SITE_ID}/reports/{created['id']}/text")
    assert r.status_code == 200
    text = r.json()["text"]
    assert "EXECUTIVE SUMMARY" in text
    assert "SITE RISK" in text
    assert "LIMITATIONS" in text


def test_intelligence_endpoint(analysis_id):
    r = client.get(f"/api/sites/{SITE_ID}/intelligence", params={"analysis_id": analysis_id})
    assert r.status_code == 200
    ctx = r.json()
    assert ctx["analysis_id"] == analysis_id
    assert "overall_risk" in ctx
    assert "critical_findings" in ctx
    assert "recommendations" in ctx
    assert ctx["site_id"] == SITE_ID

    r = client.get(f"/api/sites/{SITE_ID}/intelligence")
    assert r.status_code == 200
    assert r.json()["analysis_id"] == analysis_id


def test_history_endpoint(analysis_id):
    r = client.get(f"/api/sites/{SITE_ID}/analytics/history")
    assert r.status_code == 200
    body = r.json()
    assert body["site_id"] == SITE_ID
    assert body["count"] >= 1
    assert body["trend_available"] is False
    assert body["status"] == "INSUFFICIENT_DATA"
    assert "only one analysis" in body["message"]


def test_404s(analysis_id):
    assert client.get(f"/api/sites/{SITE_ID}/reports/no-such-report").status_code == 404
    assert client.post(
        f"/api/sites/{SITE_ID}/reports/generate",
        json={"analysis_id": "no-such-analysis"},
    ).status_code == 404
    # Unknown sites are denied by default (403) before any resource lookup —
    # the manager is not authorized for a site they cannot see.
    for path in (
        "/api/sites/no-such-site/intelligence",
        "/api/sites/no-such-site/analytics/history",
        "/api/sites/no-such-site/reports",
    ):
        assert client.get(path).status_code == 403, path


def test_reports_require_token(real_client):
    r = real_client.get(f"/api/sites/{SITE_ID}/reports")
    assert r.status_code == 401
    r = real_client.post(f"/api/sites/{SITE_ID}/reports/generate", json={})
    assert r.status_code == 401


def test_per_site_authorization_enforced(real_client):
    """Manager scoped to site_riverside_main cannot see other sites."""
    token = _login(real_client)
    headers = {"Authorization": f"Bearer {token}"}

    assert real_client.get(
        f"/api/sites/{SITE_ID}/intelligence", headers=headers
    ).status_code == 200
    for path in (
        f"/api/sites/site_elsewhere/intelligence",
        f"/api/sites/site_elsewhere/analytics/history",
        f"/api/sites/site_elsewhere/reports",
    ):
        assert real_client.get(path, headers=headers).status_code == 403, path
    assert real_client.post(
        f"/api/sites/site_elsewhere/reports/generate", json={}, headers=headers
    ).status_code == 403


def test_generated_by_records_manager(real_client):
    token = _login(real_client)
    headers = {"Authorization": f"Bearer {token}"}
    db = SessionLocal()
    try:
        manager = db.query(Manager).filter(Manager.email == DEMO_EMAIL).first()
    finally:
        db.close()

    r = real_client.post(
        f"/api/sites/{SITE_ID}/reports/generate", json={}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["generated_by"] == manager.id

    db = SessionLocal()
    try:
        stored = db.query(RiskReport).filter(
            RiskReport.id == r.json()["id"]
        ).first()
        assert stored.generated_by == manager.id
    finally:
        db.close()