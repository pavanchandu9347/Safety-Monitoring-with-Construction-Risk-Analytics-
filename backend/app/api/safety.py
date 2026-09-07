import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database.database import get_db
from app.models.models import (
    Site, Zone, Worker, Equipment, SafetyViolation, SafetyAlert, SafetyAssessment,
)
from app.schemas.schemas import (
    WorkerResponse, SafetyViolationResponse, SafetyAlertResponse,
    SafetyAssessmentResponse, SafetyDashboardResponse,
)
from app.services.simulated_data import SafetyAlertGenerator
from app.agents.safety_agent.agent import SafetyAgent
from app.services.video_analysis import get_video_report

router = APIRouter()

alert_gen = SafetyAlertGenerator()
safety_agent = SafetyAgent()


def _get_site_or_404(db: Session, site_id: str) -> Site:
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


def _build_worker_state(db: Session, site_id: str, video_report: dict | None = None) -> list[dict]:
    """Synchronize the worker register with REAL detections from the shared
    video analysis — the actual persons + PPE observed on the source video.

    The register is rebuilt on each analysis run so the safety dashboard
    reflects the same footage every module analyzes.
    """
    report = video_report or {}
    ppe_meta = report.get("ppe_workers") or {}
    workers = ppe_meta.get("workers") or []

    # Refresh persisted Worker rows from real video detections (no fabrication).
    db.query(Worker).filter(Worker.site_id == site_id).delete()
    rows: list[dict] = []
    for w in workers:
        worker_id = w.get("worker_id", f"W-{len(rows) + 1}")
        wid = f"wrk_{worker_id.lower()}"
        row = Worker(
            id=wid,
            site_id=site_id,
            name=f"Worker {worker_id}",
            role=w.get("worker_role", "worker"),
            ppe_status=w.get("ppe_status", "compliant"),
            missing_ppe=w.get("missing_ppe", []),
            detected_ppe=w.get("detected_ppe", []),
            is_present=1,
            last_seen=datetime.now(timezone.utc),
        )
        db.add(row)
        rows.append(
            {
                "worker_id": wid,
                "worker_name": row.name,
                "worker_role": row.role,
                "ppe_status": row.ppe_status,
                "detected_ppe": row.detected_ppe,
                "missing_ppe": row.missing_ppe,
            }
        )
    db.commit()
    return rows


@router.post("/sites/{site_id}/safety/analyze")
def run_safety_analysis(site_id: str, db: Session = Depends(get_db)) -> dict:
    import uuid

    _get_site_or_404(db, site_id)
    now = datetime.now(timezone.utc)

    zones = db.query(Zone).filter(Zone.site_id == site_id).all()
    equipment = (
        db.query(Equipment)
        .filter(Equipment.site_id == site_id)
        .all()
    )

    # Real detections + real per-worker PPE from the SAME configured source
    # video, not constants.
    video_report = get_video_report(site_id=site_id)
    detected_objects = video_report.get("detected_objects", [])

    zone_data = [
        {
            "zone_id": z.id,
            "zone_name": z.name,
            "risk_level": z.risk_level,
            "active_hazard_count": 0,
        }
        for z in zones
    ]

    equipment_data = [
        {
            "name": e.name,
            "equipment_type": e.equipment_type,
            "status": e.status,
            "activity": e.activity,
            "zone_id": e.zone_id,
            # Proximity risk follows the real video-detected worker count.
            "nearby_worker_count": video_report.get("worker_count", 0),
        }
        for e in equipment
    ]

    site_conditions = {
        "ground_condition": "Wet",
        "lighting_condition": "Adequate",
    }

    # Build worker PPE state from real video detections (persisted register).
    worker_ppe = _build_worker_state(db, site_id, video_report)

    result = safety_agent.analyze_site(
        worker_ppe=worker_ppe,
        equipment_data=equipment_data,
        detected_objects=detected_objects,
        site_conditions=site_conditions,
        zone_data=zone_data,
        ppe_source="ppe_detection",
    )

    ppe_res = result["ppe_compliance"]
    worker_res = result["worker_safety"]
    accident_res = result["accident_zones"].get("overall_accident_risk", {})
    safety_hazards = result["hazards"]
    unsafe_events = result["unsafe_behavior_events"]
    recs = result["recommendations"]

    # Persist SafetyViolation rows for each safety hazard.
    violation_ids = []
    for h in safety_hazards:
        violation = SafetyViolation(
            id=str(uuid.uuid4()),
            site_id=site_id,
            zone_id=None,
            worker_id=None,
            violation_type=h.get("hazard_type", "unsafe_behavior"),
            description=h.get("description", ""),
            severity=h.get("severity", "MEDIUM"),
            risk_contribution=h.get("risk_contribution", 0),
            recommended_mitigation=h.get("recommended_mitigation", ""),
            status="open",
            source=h.get("source", "ppe_detection"),
            timestamp=now,
        )
        db.add(violation)
        violation_ids.append(violation.id)

    # Also persist individual PPE violations flagged from worker assessments.
    for v in result["ppe_compliance"].get("violations", []):
        failsafe = SafetyViolation(
            id=str(uuid.uuid4()),
            site_id=site_id,
            zone_id=None,
            violation_type="ppe_violation",
            description=f"{v.get('worker_id')} missing {', '.join(v.get('missing_ppe', []) or ['PPE'])}",
            severity="HIGH",
            risk_contribution=35.0,
            recommended_mitigation="Issue replacement PPE and enforce compliance",
            status="open",
            source="ppe_detection",
            timestamp=now,
        )
        db.add(failsafe)
        violation_ids.append(failsafe.id)

    # Persist SafetyAlerts.
    alerts = alert_gen.generate(
        [{"status": "open", "severity": v.get("severity", "LOW")} for v in result["ppe_compliance"].get("violations", [])]
        + [{"status": "open", "severity": h.get("severity", "LOW")} for h in safety_hazards],
        ppe_res["compliance_rate"],
        result["overall_safety_level"],
    )
    alert_rows = []
    for a in alerts:
        alert_row = SafetyAlert(
            id=str(uuid.uuid4()),
            site_id=site_id,
            zone_id=None,
            alert_type=a["alert_type"],
            message=a["message"],
            severity=a["severity"],
            is_acknowledged=0,
            timestamp=now,
        )
        db.add(alert_row)
        alert_rows.append(alert_row)

    # Persist SafetyAssessment.
    assessment = SafetyAssessment(
        id=str(uuid.uuid4()),
        site_id=site_id,
        timestamp=now,
        overall_safety_score=result["overall_safety_score"],
        overall_safety_level=result["overall_safety_level"],
        ppe_score=ppe_res["score"],
        ppe_compliance_rate=ppe_res["compliance_rate"],
        worker_safety_score=worker_res["score"],
        worker_count=len(worker_ppe),
        accident_zone_score=accident_res.get("score", 0),
        ppe_factors=ppe_res["factors"],
        worker_factors=worker_res["factors"],
        accident_factors=accident_res.get("factors", []),
        violation_count=len(violation_ids),
        alert_count=len(alert_rows),
        summary=result["summary"],
    )
    db.add(assessment)
    db.commit()

    return {
        "safety_assessment": SafetyAssessmentResponse.model_validate(assessment).model_dump(),
        "workers": worker_ppe,
        "ppe_compliance": ppe_res,
        "accident_zones": result["accident_zones"],
        "unsafe_behavior_events": unsafe_events,
        "violations_count": len(violation_ids),
        "alerts_count": len(alert_rows),
        "recommendations_count": len(recs),
    }


@router.get("/sites/{site_id}/safety/dashboard", response_model=SafetyDashboardResponse)
def get_safety_dashboard(site_id: str, db: Session = Depends(get_db)):
    site = _get_site_or_404(db, site_id)

    assessment = (
        db.query(SafetyAssessment)
        .filter(SafetyAssessment.site_id == site_id)
        .order_by(SafetyAssessment.timestamp.desc())
        .first()
    )
    workers = db.query(Worker).filter(Worker.site_id == site_id).all()
    violations = (
        db.query(SafetyViolation)
        .filter(SafetyViolation.site_id == site_id)
        .order_by(SafetyViolation.timestamp.desc())
        .limit(50)
        .all()
    )
    alerts = (
        db.query(SafetyAlert)
        .filter(SafetyAlert.site_id == site_id)
        .order_by(SafetyAlert.timestamp.desc())
        .limit(20)
        .all()
    )

    # Aggregate accident-zone data from stored assessment (best-effort).
    zones = db.query(Zone).filter(Zone.site_id == site_id).all()
    accident_zone_data = [
        {
            "zone_id": z.id,
            "zone_name": z.name,
            "risk_level": z.risk_level,
            "current_risk_score": z.current_risk_score,
        }
        for z in zones
    ]

    compliant = sum(1 for w in workers if w.ppe_status == "compliant")
    total_workers = len(workers)
    open_violations = sum(1 for v in violations if v.status == "open")
    critical_alerts = sum(1 for a in alerts if a.severity == "CRITICAL")

    return SafetyDashboardResponse(
        site_id=site_id,
        site_name=site.name,
        generated_at=datetime.now(timezone.utc),
        current_safety_assessment=assessment,
        workers=[WorkerResponse.model_validate(w) for w in workers],
        violations=[SafetyViolationResponse.model_validate(v) for v in violations],
        alerts=[SafetyAlertResponse.model_validate(a) for a in alerts],
        accident_zone_data=accident_zone_data,
        unsafe_behavior_events=[],
        total_workers=total_workers,
        compliant_workers=compliant,
        violation_count=len(violations),
        open_violations=open_violations,
        critical_alerts=critical_alerts,
        compliance_rate=round(compliant / total_workers, 3) if total_workers else 1.0,
    )


@router.get("/sites/{site_id}/workers", response_model=list[WorkerResponse])
def list_workers(site_id: str, db: Session = Depends(get_db)):
    return db.query(Worker).filter(Worker.site_id == site_id).limit(100).all()


@router.get("/sites/{site_id}/safety/violations", response_model=list[SafetyViolationResponse])
def list_violations(site_id: str, severity: str = "", db: Session = Depends(get_db)):
    q = db.query(SafetyViolation).filter(SafetyViolation.site_id == site_id)
    if severity:
        q = q.filter(SafetyViolation.severity == severity.upper())
    return q.order_by(SafetyViolation.timestamp.desc()).limit(100).all()


@router.get("/sites/{site_id}/safety/alerts", response_model=list[SafetyAlertResponse])
def list_alerts(site_id: str, db: Session = Depends(get_db)):
    return (
        db.query(SafetyAlert)
        .filter(SafetyAlert.site_id == site_id)
        .order_by(SafetyAlert.timestamp.desc())
        .limit(50)
        .all()
    )


@router.patch("/safety/violations/{violation_id}/status")
def update_violation_status(violation_id: str, status: str = "resolved", db: Session = Depends(get_db)):
    violation = db.query(SafetyViolation).filter(SafetyViolation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    violation.status = status
    if status == "resolved":
        violation.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(violation)
    return SafetyViolationResponse.model_validate(violation)
