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
from app.services.analysis_pipeline import run_analysis, build_analysis_response, get_latest_analysis

router = APIRouter()


def _get_site_or_404(db: Session, site_id: str) -> Site:
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.post("/sites/{site_id}/safety/analyze")
def run_safety_analysis(site_id: str, db: Session = Depends(get_db)) -> dict:
    """Run (or reuse) the unified video analysis and return its safety payload.

    All safety results come from the shared pipeline so they carry the same
    ``analysis_id`` and video-derived evidence as risk, monitoring, and
    equipment results.
    """
    _get_site_or_404(db, site_id)

    result = run_analysis(db, site_id=site_id)
    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))

    return {
        "status": "success",
        "analysis_id": result["analysis_id"],
        "safety_assessment": result.get("safety", {}),
        "workers": result.get("workers", []),
        "ppe_compliance": result.get("safety", {}).get("ppe_compliance", {}),
        "violations": result.get("violations", []),
        "alerts": result.get("alerts", []),
        "recommendations_count": len(result.get("recommendations", [])),
        "evidence_note": result.get("evidence_note", ""),
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
