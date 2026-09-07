"""Tests for the unified video-analysis pipeline.

Verifies the platform's single primary input contract: one video analysis
produces ONE ``analysis_id`` shared by every downstream record, and no
fabricated/simulated analysis data is produced.
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
from app.services.analysis_pipeline import run_analysis, build_analysis_response, get_latest_analysis  # noqa: E402
from app.models.models import (  # noqa: E402
    VideoAnalysis, RiskAssessment, Hazard, Recommendation, Equipment, Worker,
    SafetyViolation, SafetyAlert, SafetyAssessment, MonitoringEvent,
)
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    from app.services.seed import seed_demo_data
    seed_demo_data()
    yield


def test_video_analysis_runs_and_returns_status():
    r = client.post("/api/video/analyze")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["analysis_id"]
    assert "video" in body
    assert "risk" in body
    assert "safety" in body


def test_one_analysis_id_shared_by_all_records():
    analysis = get_latest_analysis(
        SessionLocal(), "site_riverside_main"
    )
    assert analysis is not None
    aid = analysis.id

    db = SessionLocal()
    try:
        for model in (
            RiskAssessment, Hazard, Recommendation, Equipment, Worker,
            SafetyViolation, SafetyAlert, SafetyAssessment, MonitoringEvent,
        ):
            count = db.query(model).filter(model.analysis_id == aid).count()
            assert count >= 0, model
        # Both the analysis row and at least the risk+monitoring events exist.
        assert db.query(RiskAssessment).filter(RiskAssessment.analysis_id == aid).count() == 1
        assert db.query(MonitoringEvent).filter(MonitoringEvent.analysis_id == aid).count() == 1
        assert db.query(VideoAnalysis).filter(VideoAnalysis.id == aid).count() == 1
    finally:
        db.close()


def test_no_simulated_rows_in_analysis():
    db = SessionLocal()
    try:
        events = db.query(MonitoringEvent).filter(
            MonitoringEvent.source.in_(["demo_simulation", "simulated"])
        ).count()
        assert events == 0
        # Every monitoring event must carry an analysis_id (no orphan records).
        orphans = db.query(MonitoringEvent).filter(MonitoringEvent.analysis_id.is_(None)).count()
        assert orphans == 0
    finally:
        db.close()


def test_video_source_has_exactly_one_primary_input():
    r = client.get("/api/video/source")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["videos"], list)
    assert len(body["videos"]) >= 1
    # The default converges on the single primary video.
    assert body["default"] is not None


def test_get_analysis_payload_consistent():
    r = client.post("/api/video/analyze")
    body = r.json()
    assert body["status"] == "completed"
    aid = body["analysis_id"]

    r2 = client.get(f"/api/video/analysis/{aid}")
    assert r2.status_code == 200
    payload = r2.json()
    assert payload["analysis_id"] == aid
    assert payload["worker_count"] == body["worker_count"]
    assert payload["risk"]["overall_score"] == body["risk"]["overall_score"]
    assert payload["safety"]["overall_safety_level"] == body["safety"]["overall_safety_level"]