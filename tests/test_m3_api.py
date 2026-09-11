"""Integration tests for Milestone 3 — Compliance & Insurance API.

Runs the unified video pipeline once and verifies that compliance and
insurance records share the same ``analysis_id`` as safety/risk, that the
dashboards reflect the persisted records, and that all M3 endpoints respond.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ["TESTING"] = "1"
from app.main import app  # noqa: E402
from app.database.database import (  # noqa: E402
    Base, engine, SessionLocal, init_db,
)
from app.services.analysis_pipeline import run_analysis  # noqa: E402
from app.models.models import (  # noqa: E402
    ComplianceFinding, ComplianceAssessment, ComplianceRequirement, InspectionRecord,
    InsuranceAssessment, InsuranceIncident, ClaimRecord, SafetyViolation,
)
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

SITE_ID = "site_riverside_main"


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


def test_m3_assessments_return_shared_analysis_id(analysis_id):
    """Verify compliance/insurance assessments reference the same analysis_id."""
    r = client.get(f"/api/sites/{SITE_ID}/compliance/assessment")
    assert r.status_code == 200
    assert r.json()["analysis_id"] == analysis_id

    r2 = client.get(f"/api/sites/{SITE_ID}/insurance/assessment")
    assert r2.status_code == 200
    assert r2.json()["analysis_id"] == analysis_id


def test_m3_records_share_analysis_id(analysis_id):
    db = SessionLocal()
    try:
        assert db.query(ComplianceAssessment).filter(
            ComplianceAssessment.analysis_id == analysis_id
        ).count() == 1
        assert db.query(InsuranceAssessment).filter(
            InsuranceAssessment.analysis_id == analysis_id
        ).count() == 1
        assert db.query(ComplianceFinding).filter(
            ComplianceFinding.analysis_id == analysis_id
        ).count() >= 1
        assert db.query(InspectionRecord).filter(
            InspectionRecord.site_id == SITE_ID
        ).count() == 4
    finally:
        db.close()


def test_inspection_status_reflects_tracker(analysis_id):
    db = SessionLocal()
    try:
        daily = db.query(InspectionRecord).filter(
            InspectionRecord.site_id == SITE_ID,
            InspectionRecord.inspection_type == "Daily site walkthrough",
        ).first()
        assert daily is not None
        assert daily.status in ("OVERDUE", "COMPLETED", "NOT_AVAILABLE", "DUE")
        # No completed inspection can be assumed without a real record.
        completed = db.query(InspectionRecord).filter(
            InspectionRecord.site_id == SITE_ID,
            InspectionRecord.status == "COMPLETED",
        ).count()
        assert completed == 0
    finally:
        db.close()


def test_compliance_dashboard():
    r = client.get(f"/api/sites/{SITE_ID}/compliance/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["site_id"] == SITE_ID
    assert body["total_requirements"] == 15
    assert len(body["inspections"]) == 4
    assert body["current_assessment"] is not None
    assert body["current_assessment"]["requirements_checked"] > 0
    assert body["compliant"] + body["non_compliant"] + body["not_verified"] == len(body["findings"])


def test_compliance_list_endpoints():
    for path in (
        f"/api/sites/{SITE_ID}/compliance/findings",
        f"/api/sites/{SITE_ID}/compliance/requirements",
        f"/api/sites/{SITE_ID}/compliance/inspections",
        f"/api/sites/{SITE_ID}/compliance/assessment",
    ):
        r = client.get(path)
        assert r.status_code == 200, path
        if "assessment" in path:
            assert r.json()["analysis_id"]
        else:
            assert isinstance(r.json(), list)


def test_insurance_dashboard():
    r = client.get(f"/api/sites/{SITE_ID}/insurance/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["incident_count"] >= 0
    assert isinstance(body["incidents"], list)
    assert isinstance(body["claim_records"], list)
    assert "claim_documentation" in body


def test_insurance_list_endpoints(analysis_id):
    db = SessionLocal()
    try:
        expected_incidents = db.query(InsuranceIncident).filter(
            InsuranceIncident.analysis_id == analysis_id
        ).count()
        expected_claims = db.query(ClaimRecord).filter(
            ClaimRecord.analysis_id == analysis_id
        ).count()
    finally:
        db.close()

    r = client.get(f"/api/sites/{SITE_ID}/insurance/incidents")
    assert r.status_code == 200
    assert len(r.json()) >= expected_incidents

    r = client.get(f"/api/sites/{SITE_ID}/insurance/claims")
    assert r.status_code == 200
    assert len(r.json()) == expected_claims

    r = client.get(f"/api/sites/{SITE_ID}/insurance/assessment")
    assert r.status_code == 200
    assert r.json()["analysis_id"] == analysis_id


def test_post_compliance_analyze():
    r = client.post(f"/api/sites/{SITE_ID}/compliance/analyze")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["analysis_id"]
    assert body["compliance"]["requirements_checked"] > 0


def test_post_insurance_analyze():
    r = client.post(f"/api/sites/{SITE_ID}/insurance/analyze")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["analysis_id"]
    assert "insurance_risk_score" in body