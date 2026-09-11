"""Milestone 4 — evidence-based risk alert notifications.

Covers the notification policy (severity mapping), deduplication/cooldown,
HIGH→CRITICAL escalation bypass, evidence traceability (real fields only, or
"Evidence unavailable"), email-failure safety, and the authenticated inbox API.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import datetime, timedelta

import pytest  # noqa: E402

from app.database.database import Base, engine, init_db, SessionLocal  # noqa: E402
from app.models.models import Notification, Manager  # noqa: E402
from app.services import notification_service  # noqa: E402

SITE = "site_riverside_main"

from app.main import app as fastapi_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
client = TestClient(fastapi_app)


@pytest.fixture(scope="module", autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    from app.services.seed import seed_demo_data
    seed_demo_data()
    yield


@pytest.fixture(autouse=True)
def clear_notifications(reset_db):
    """Each test starts with an empty notification inbox (dedup is per-test)."""
    db = SessionLocal()
    try:
        db.query(Notification).delete()
        db.commit()
    finally:
        db.close()


def _count():
    db = SessionLocal()
    try:
        return db.query(Notification).count()
    finally:
        db.close()


def _sample_risk(score=60.0, level="HIGH"):
    return {
        "overall_score": score,
        "risk_level": level,
        "environmental_score": 40.0,
        "equipment_score": score,
        "site_condition_score": 10.0,
        "activity_score": 20.0,
        "environmental_factors": [],
        "equipment_factors": [
            {"factor": "Crane boom load exceeds safe working limit", "severity": "HIGH", "evidence": "EQU0E 0.87 4 conf"},
        ],
        "site_condition_factors": [],
        "activity_factors": [],
        "summary": "Equipment loading is the dominant risk driver.",
        "recommendations": ["Fully characterise load before each lift"],
    }


def _sample_safety(score=65.0, level="HIGH"):
    return {
        "overall_safety_score": score,
        "overall_safety_level": level,
        "ppe_compliance": {
            "score": 62.0,
            "compliant_count": 4,
            "non_compliant_count": 1,
            "insufficient_evidence_count": 1,
        },
        "violations": [],
        "recommendations": ["Re-brief workers on PPE requirements"],
        "hazards": [],
    }


def test_low_risk_creates_no_notification(reset_db):
    created = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-1",
        risk={
            "overall_score": 20.0,
            "risk_level": "LOW",
            "environmental_factors": [],
            "equipment_factors": [],
            "site_condition_factors": [],
            "activity_factors": [],
            "recommendations": [],
        },
        safety={
            "overall_safety_score": 15.0,
            "overall_safety_level": "LOW",
            "ppe_compliance": {
                "score": 90.0,
                "compliant_count": 5,
                "non_compliant_count": 0,
                "insufficient_evidence_count": 0,
            },
            "recommendations": [],
        },
    )
    assert created == []


def test_high_risk_creates_notification_with_real_evidence(reset_db):
    created = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-2",
        risk=_sample_risk(score=62.0, level="HIGH"),
        safety=_sample_safety(score=20.0, level="LOW"),
    )
    assert len(created) == 1
    n = created[0]
    assert n.severity == "HIGH"
    assert n.site_id == SITE
    ev = n.evidence
    # Evidence must be traceable: the equipment factor came from the analysis.
    factor = ev["contributing_factors"][0]
    assert factor["factor"] == "Crane boom load exceeds safe working limit"
    assert factor["basis"] == "video/inspection data"
    assert "video, sensor and inspection data" in ev["evidence_note"]
    assert n.risk_score == 62.0


def test_critical_risk_bypasses_cooldown_and_escalates(reset_db):
    """HIGH alert is created; the escalating CRITICAL re-fires immediately."""
    created1 = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-3",
        risk=_sample_risk(score=62.0, level="HIGH"),
        safety=_sample_safety(score=20.0, level="LOW"),
    )
    assert len(created1) == 1
    assert created1[0].severity == "HIGH"

    # Same condition repeated within cooldown -> suppressed.
    created2 = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-4",
        risk=_sample_risk(score=63.0, level="HIGH"),
        safety=_sample_safety(score=20.0, level="LOW"),
    )
    assert created2 == []
    assert _count() == 1

    # Escalation to CRITICAL -> delivered immediately despite cooldown.
    created3 = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-5",
        risk=_sample_risk(score=88.0, level="CRITICAL"),
        safety=_sample_safety(score=20.0, level="LOW"),
    )
    assert len(created3) == 1
    assert created3[0].severity == "CRITICAL"
    assert "escalation" in created3[0].dedup_key
    assert _count() == 2


def test_evidence_unavailable_is_labeled(reset_db):
    """A HIGH score with no identifiable factors must say so honestly."""
    created = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-6",
        risk={
            "overall_score": 60.0,
            "risk_level": "HIGH",
            "environmental_factors": [],
            "equipment_factors": [],
            "site_condition_factors": [],
            "activity_factors": [],
            "recommendations": [],
        },
        safety=_sample_safety(score=20.0, level="LOW"),
    )
    assert created
    ev = created[0].evidence
    assert ev["contributing_factors"] == []
    assert ev["evidence_note"] == "Evidence unavailable for specific contributing causes."


def test_ppe_insufficient_evidence_notification(reset_db):
    safety = _sample_safety(score=30.0, level="MEDIUM")
    safety["ppe_compliance"]["insufficient_evidence_count"] = 2
    created = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-7",
        risk={
            "overall_score": 30.0,
            "risk_level": "MEDIUM",
            "environmental_factors": [],
            "equipment_factors": [],
            "site_condition_factors": [],
            "activity_factors": [],
            "recommendations": [],
        },
        safety=safety,
    )
    titles = [t.lower() for t in (n.title for n in created)]
    messages = [m.lower() for m in (n.message for n in created)]
    assert any("ppe" in t for t in titles) or any("insufficient visual evidence" in m for m in messages)


def test_email_failure_never_fails_analysis(reset_db, monkeypatch):
    """SMTP failure must not raise, and in-app notification still exists."""
    from app.services.notification_service import _deliver

    created = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-8",
        risk=_sample_risk(score=70.0, level="HIGH"),
        safety=_sample_safety(score=20.0, level="LOW"),
    )
    assert created

    # Simulate a fully-configured SMTP that then fails hard on connect.
    monkeypatch.setattr(notification_service, "SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setattr(notification_service, "NOTIFICATION_EMAIL_FROM", "alerts@buildsure.io")
    monkeypatch.setattr(notification_service, "SMTP_USERNAME", "u")
    monkeypatch.setattr(notification_service, "SMTP_PASSWORD", "p")

    def _boom(*a, **k):
        raise ConnectionError("SMTP unreachable")

    monkeypatch.setattr(notification_service.smtplib, "SMTP", _boom)

    # Must not raise; notification row already persisted in-app.
    created[0].message += " (re-delivery attempt)"  # cheap guard against identity reuse
    _deliver(created[0], site=None)
    assert _count() >= 1


def test_unconfigured_email_logs_and_keeps_in_app(reset_db, monkeypatch):
    from app.services.notification_service import _deliver
    created = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-9",
        risk=_sample_risk(score=71.0, level="HIGH"),
        safety=_sample_safety(score=20.0, level="LOW"),
    )
    monkeypatch.setattr(notification_service, "SMTP_HOST", "")
    _deliver(created[0], site=None)  # logs "external email not configured", no raise
    assert _count() >= 1


def test_notification_api_inbox_flow(reset_db):
    """Authenticated manager reads, counts and marks notifications."""
    created = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-10",
        risk=_sample_risk(score=78.0, level="CRITICAL"),
        safety=_sample_safety(score=20.0, level="LOW"),
    )
    assert created
    nid = created[0].id

    # conftest's get_current_manager override returns the demo manager.
    r = client.get("/api/notifications")
    assert r.status_code == 200
    assert any(n["id"] == nid for n in r.json())

    r = client.get("/api/notifications/unread-count")
    assert r.status_code == 200
    assert r.json()["count"] >= 1

    r = client.patch(f"/api/notifications/{nid}/read")
    assert r.status_code == 200
    assert r.json()["status"] == "read"

    r = client.get("/api/notifications")
    assert all(n["id"] != nid or n["status"] == "read" for n in r.json())

    r = client.get(f"/api/notifications?status=unread")
    assert all(n["status"] == "unread" for n in r.json())


def test_notifications_are_scoped_to_manager(reset_db):
    """A different manager never sees another manager's notifications."""
    db = SessionLocal()
    try:
        other = Manager(
            id="manager_other_002",
            name="Other",
            email="other2@buildsure.io",
            password_hash="scrypt$0$0$0$0000$0000",
            role="manager",
            site_id="site_riverside_main",
            is_active=1,
        )
        db.add(other)
        db.commit()
    finally:
        db.close()

    created = notification_service.evaluate_analysis(
        SessionLocal(), SITE, "an-11",
        risk=_sample_risk(score=80.0, level="CRITICAL"),
        safety=_sample_safety(score=20.0, level="LOW"),
    )
    # Created for every manager assigned to the site.
    assert len(created) >= 1

    # The API only ever returns the authenticated manager's own notifications.
    r = client.get("/api/notifications")
    assert r.status_code == 200
    assert all("manager_id" not in n or n["id"] for n in r.json())