"""Milestone 4 — Reporting Agent, report generation & persistence.

Verifies the Reporting Agent consumes the intelligence context (never re-runs
models), every report references one real analysis, reports only contain
evidence-backed facts, and trend analysis honors real analysis history.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest  # noqa: E402

os.environ["TESTING"] = "1"
from app.database.database import Base, engine, init_db, SessionLocal  # noqa: E402
from app.services.analysis_pipeline import run_analysis  # noqa: E402
from app.services.report_service import generate_report, report_to_dict, render_text  # noqa: E402
from app.models.models import RiskReport, Manager, ClaimRecord  # noqa: E402

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


@pytest.fixture(scope="module")
def second_analysis_id(analysis_id):
    db = SessionLocal()
    try:
        result = run_analysis(db, site_id=SITE_ID)
    finally:
        db.close()
    assert result["status"] == "completed"
    return result["analysis_id"]


@pytest.fixture
def manager_id():
    db = SessionLocal()
    try:
        return db.query(Manager).filter(
            Manager.email == "manager@buildsure.io"
        ).first().id
    finally:
        db.close()


def test_generate_report_persists_and_is_traceable(analysis_id, manager_id):
    db = SessionLocal()
    try:
        report = generate_report(
            db, SITE_ID, analysis_id, generated_by=manager_id,
        )
        assert report.analysis_id == analysis_id
        assert report.site_id == SITE_ID
        assert report.status == "completed"
        assert report.generated_by == manager_id

        content = report.content
        assert content["analysis_id"] == analysis_id
        assert content["site_id"] == SITE_ID
        assert content["generated_at"]
        assert content["site_info"]["site_id"] == SITE_ID
        assert content["analysis_info"]["analysis_id"] == analysis_id
        assert isinstance(content["limitations"], list) and content["limitations"]
        assert "executive_summary" in content
        assert {"risk", "safety", "compliance", "insurance"} <= set(content["sections"].keys())
        assert isinstance(report.summary, str) and report.summary
    finally:
        db.close()


def test_prioritized_actions_only_from_real_sources(analysis_id):
    db = SessionLocal()
    try:
        content = generate_report(db, SITE_ID, analysis_id).content
    finally:
        db.close()
    allowed = {"site_risk_agent", "compliance_intelligence", "insurance_intelligence", "safety_intelligence"}
    for action in content["prioritized_actions"]:
        assert action["source"] in allowed


def test_report_never_invents_claims(analysis_id):
    db = SessionLocal()
    try:
        content = generate_report(db, SITE_ID, analysis_id).content
        persisted_claims = db.query(ClaimRecord).filter(
            ClaimRecord.analysis_id == analysis_id
        ).count()
    finally:
        db.close()
    insurance = content["sections"]["insurance"]
    assert insurance["claim_records"] == persisted_claims


def test_report_to_dict_and_render(analysis_id):
    db = SessionLocal()
    try:
        report = generate_report(db, SITE_ID, analysis_id)
        payload = report_to_dict(db, report)
        assert payload["id"] == report.id
        assert payload["analysis_id"] == analysis_id
        assert payload["content"]["executive_summary"]["overall_risk_level"] in (
            "LOW", "MEDIUM", "HIGH", "CRITICAL", "NOT_AVAILABLE",
        )
        text = render_text(db, report)
        assert isinstance(text, str) and "EXECUTIVE SUMMARY" in text
        assert "SITE RISK" in text
        assert "RECOMMENDATIONS (PRIORITIZED ACTIONS)" in text
        assert "LIMITATIONS" in text
    finally:
        db.close()


def test_trend_available_with_two_analyses(second_analysis_id):
    """Two real analyses -> report trend is AVAILABLE with a direction."""
    db = SessionLocal()
    try:
        content = generate_report(db, SITE_ID, second_analysis_id).content
    finally:
        db.close()
    hist = content["historical_analytics"]
    assert hist["status"] == "AVAILABLE"
    assert hist["trend_available"] is True
    assert hist["direction"] in ("improving", "worsening", "stable")


def test_second_report_is_a_new_row(analysis_id, second_analysis_id):
    db = SessionLocal()
    try:
        r1 = generate_report(db, SITE_ID, analysis_id)
        r2 = generate_report(db, SITE_ID, second_analysis_id)
        assert r1.id != r2.id
        count = db.query(RiskReport).filter(
            RiskReport.site_id == SITE_ID
        ).count()
        assert count >= 2
    finally:
        db.close()


def test_missing_analysis_prevents_report(manager_id):
    db = SessionLocal()
    try:
        from app.services.intelligence import AnalysisNotFoundError
        with pytest.raises(AnalysisNotFoundError):
            generate_report(db, SITE_ID, "no-such-analysis", generated_by=manager_id)
    finally:
        db.close()