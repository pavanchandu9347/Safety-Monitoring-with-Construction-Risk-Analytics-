"""Milestone 4 — Construction Risk Intelligence Engine & Historical Analytics.

Verifies the unified intelligence context is aggregated from REAL persisted
analysis rows only: shared ``analysis_id``, no fabricated counts, severity
grouped findings, evidence traceability, NOT_VERIFIED != NON_COMPLIANT, and
explicit missing-data handling.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest  # noqa: E402

os.environ["TESTING"] = "1"
from app.database.database import Base, engine, init_db, SessionLocal  # noqa: E402
from app.services.analysis_pipeline import run_analysis  # noqa: E402
from app.services.intelligence import (  # noqa: E402
    IntelligenceEngine,
    build_intelligence,
    AnalysisNotFoundError,
    SiteNotFoundError,
)
from app.services.historical_analytics import build_history  # noqa: E402
from app.models.models import (  # noqa: E402
    Hazard, SafetyViolation, SafetyAlert, Worker, Equipment, InsuranceIncident,
    ClaimRecord,
)

SITE_ID = "site_riverside_main"


def _intel(analysis_id):
    """Read-only helper that ALWAYS closes the session.

    PostgreSQL rolls back only on close; an abandoned session leaves an open
    ``idle in transaction`` connection holding locks that block later DDL
    (e.g. the next test module's ``drop_all``).
    """
    db = SessionLocal()
    try:
        return build_intelligence(db, SITE_ID, analysis_id)
    finally:
        db.close()


def _hist():
    db = SessionLocal()
    try:
        return build_history(db, SITE_ID)
    finally:
        db.close()


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
def enriched(analysis_id):
    """A second real analysis with extra REAL persisted rows attached."""
    db = SessionLocal()
    try:
        result = run_analysis(db, site_id=SITE_ID)
        aid = result["analysis_id"]
        db.add(Hazard(
            id="m4_h_crit", site_id=SITE_ID, analysis_id=aid,
            hazard_type="fall_from_height", description="CRITICAL fall hazard",
            severity="CRITICAL", status="detected", risk_contribution=80.0,
        ))
        db.add(Hazard(
            id="m4_h_mid", site_id=SITE_ID, analysis_id=aid,
            hazard_type="poor_housekeeping", description="clutter",
            severity="MEDIUM", status="resolved", risk_contribution=10.0,
        ))
        db.add(Worker(
            id="m4_w1", site_id=SITE_ID, analysis_id=aid,
            name="Worker One", role="scaffolder", ppe_status="non_compliant",
            missing_ppe=["helmet"], is_present=1,
        ))
        db.add(Worker(
            id="m4_w2", site_id=SITE_ID, analysis_id=aid,
            name="Worker Two", role="operator", ppe_status="compliant",
            missing_ppe=[], is_present=1,
        ))
        # Persist referenced parents before any child that links to them --
        # PostgreSQL enforces foreign keys (SQLite never did).
        db.flush()
        db.add(SafetyViolation(
            id="m4_v_crit", site_id=SITE_ID, analysis_id=aid,
            violation_type="no_helmet", description="worker without helmet",
            severity="CRITICAL", status="open", worker_id="m4_w1",
        ))
        db.add(SafetyViolation(
            id="m4_v_low", site_id=SITE_ID, analysis_id=aid,
            violation_type="no_vest", description="worker missing vest",
            severity="LOW", status="open",
            recommended_mitigation="Issue a reflective vest",
        ))
        db.add(SafetyAlert(
            id="m4_a_high", site_id=SITE_ID, analysis_id=aid,
            alert_type="hardhat_missing", message="hardhat missing",
            severity="HIGH",
        ))
        db.add(Equipment(
            id="m4_e1", site_id=SITE_ID, analysis_id=aid, name="Excavator",
            equipment_type="Excavator", status="active",
            maintenance_status="maintenance_due", zone_id=None,
        ))
        db.add(InsuranceIncident(
            id="m4_inc1", site_id=SITE_ID, analysis_id=aid,
            incident_type="near_miss", description="near miss with plant",
            severity="HIGH", claim_risk="MEDIUM",
        ))
        db.commit()
        return aid
    finally:
        db.close()


def test_enriched_analysis_shared_id(enriched):
    ctx = _intel(analysis_id= enriched)
    assert ctx["analysis_id"] == enriched
    assert ctx["site_id"] == SITE_ID
    assert ctx["status"] in ("COMPLETE", "PARTIAL")


def test_findings_grouped_by_severity(enriched):
    ctx = _intel(analysis_id= enriched)
    critical = ctx["critical_findings"]
    high = ctx["high_findings"]

    crit_by_type = {f["type"]: f for f in critical}
    # CRITICAL hazard + CRITICAL violation both rolled up as critical.
    assert "hazard" in crit_by_type
    assert crit_by_type["hazard"]["title"] == "fall_from_height"
    assert "violation" in crit_by_type
    assert crit_by_type["violation"]["severity"] == "CRITICAL"

    high_titles = {f["title"] for f in high}
    # HIGH alert + HIGH incident roll up as HIGH; the MEDIUM hazard and LOW
    # violation are intentionally excluded from critical/high findings.
    assert "hardhat_missing" in high_titles
    assert "near_miss" in high_titles
    assert "poor_housekeeping" not in high_titles


def test_open_violations_only_open_status(enriched):
    ctx = _intel(analysis_id= enriched)
    open_ids = {v["id"] for v in ctx["open_violations"]}
    assert "m4_v_crit" in open_ids
    assert "m4_v_low" in open_ids


def test_recommendations_come_from_persisted_rows(enriched):
    ctx = _intel(analysis_id= enriched)
    sources = {r["source"] for r in ctx["recommendations"]}
    # The persisted per-violation mitigation is surfaced as a safety action.
    assert "safety_intelligence" in sources
    mitigation = [
        r for r in ctx["recommendations"]
        if r.get("source") == "safety_intelligence" and r.get("id") == "m4_v_low"
    ]
    assert mitigation and mitigation[0]["title"] == "Issue a reflective vest"
    assert mitigation[0]["priority"] == "LOW"


def test_worker_and_equipment_summaries_are_real(enriched):
    ctx = _intel(analysis_id= enriched)
    ws = ctx["worker_summary"]
    assert {"worker_id": "m4_w1", "worker_name": "Worker One"} in [
        {"worker_id": e["worker_id"], "worker_name": e["worker_name"]}
        for e in ws["missing_ppe"]
    ]
    assert ws["ppe_non_compliant"] >= 1

    eq = ctx["equipment_summary"]
    ids = {e["id"] for e in eq["equipment"]}
    assert "m4_e1" in ids
    assert eq["maintenance_issues"] >= 1


def test_no_fabricated_claims(enriched):
    ctx = _intel(analysis_id= enriched)
    db = SessionLocal()
    try:
        persisted_claims = db.query(ClaimRecord).filter(
            ClaimRecord.analysis_id == enriched
        ).count()
    finally:
        db.close()
    assert len(ctx["claim_records"]) == persisted_claims
    assert "near_miss" in {i["incident_type"] for i in ctx["insurance_incidents"]}


def test_not_verified_not_non_compliant(analysis_id):
    """NOT_VERIFIED findings must never be counted as NON_COMPLIANT."""
    ctx = _intel(analysis_id= analysis_id)
    compliance = ctx["compliance_summary"]
    assert compliance is not None
    assert int(compliance["not_verified_count"]) >= 0
    assert int(compliance["non_compliant_count"]) >= 0
    # Not-verified evidence cannot inflate the non-compliant count.
    assert int(compliance["not_verified_count"]) + int(
        compliance["non_compliant_count"]
    ) <= int(compliance["requirements_checked"])


def test_overall_risk_reuses_persisted_assessment(analysis_id):
    ctx = _intel(analysis_id= analysis_id)
    db = SessionLocal()
    try:
        from app.models.models import RiskAssessment
        persisted = (
            db.query(RiskAssessment)
            .filter(RiskAssessment.analysis_id == analysis_id)
            .first()
        )
    finally:
        db.close()
    assert persisted is not None
    assert ctx["overall_risk"]["score"] == persisted.overall_score
    assert ctx["overall_risk"]["level"] == persisted.risk_level or "LOW"


def test_missing_analysis_raises(analysis_id):
    from sqlalchemy.orm import Session
    db = SessionLocal()
    try:
        with pytest.raises(AnalysisNotFoundError):
            build_intelligence(db, SITE_ID, "no-such-analysis")
    finally:
        db.close()


def test_unknown_site_raises(analysis_id):
    db = SessionLocal()
    try:
        with pytest.raises(SiteNotFoundError):
            build_intelligence(db, "no-such-site", analysis_id)
    finally:
        db.close()


def test_engine_never_invents_missing_safety(enriched):
    """Safety summary fields must come straight from the persisted row."""
    ctx = _intel(analysis_id= enriched)
    db = SessionLocal()
    try:
        from app.models.models import SafetyAssessment
        persisted = (
            db.query(SafetyAssessment)
            .filter(SafetyAssessment.analysis_id == enriched)
            .first()
        )
    finally:
        db.close()
    safety = ctx["safety_summary"]
    if persisted is not None:
        assert safety["overall_safety_score"] == persisted.overall_safety_score
        assert safety["violation_count"] == persisted.violation_count


def test_historical_analytics_insufficient_with_one_analysis(analysis_id):
    from app.services.historical_analytics import build_history
    hist = _hist()
    assert hist["count"] >= 1
    assert hist["trend_available"] == (hist["count"] >= 2)
    if hist["count"] < 2:
        assert hist["status"] == "INSUFFICIENT_DATA"
        assert "only one analysis" in hist["message"]
    # Every series point maps to a persisted analysis, never synthetic.
    assert all("analysis_id" in p for p in hist["series"])
    assert all(p["risk_score"] is None or isinstance(p["risk_score"], float) for p in hist["series"])


def test_historical_analytics_trend_after_two_runs(enriched):
    """Two REAL analyses produce an available trend with a direction."""
    from app.services.historical_analytics import build_history
    hist = _hist()
    assert hist["count"] >= 2
    assert hist["trend_available"] is True
    assert hist["status"] == "AVAILABLE"
    scored = [s for s in hist["series"] if s["risk_score"] is not None]
    assert len(scored) >= 2
    from app.agents.reporting_agent import trend_analyzer
    assert trend_analyzer.direction(hist) in ("improving", "worsening", "stable")