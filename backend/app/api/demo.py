import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.models import (
    Project, Site, Zone
)
from app.services.analysis_pipeline import (
    run_analysis, build_analysis_response, get_latest_analysis,
)

router = APIRouter()


@router.post("/demo/generate")
def generate_demo_analysis(site_id: str = "site_riverside_main", db: Session = Depends(get_db)):
    """Generate the dashboard by running the unified video pipeline.

    This is no longer a simulation: it analyzes the single configured
    construction-site video and persists one coherent ``analysis_id``.
    """
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        project = Project(
            id="proj_riverside_001",
            name="Riverside Tower Complex",
            description="Mixed-use high-rise development",
            location="123 Riverside Drive, Metro City",
        )
        db.add(project)
        site = Site(id=site_id, project_id="proj_riverside_001", name="Riverside Tower Main Site")
        db.add(site)
        db.commit()

    existing_zones = db.query(Zone).filter(Zone.site_id == site_id).all()
    if not existing_zones:
        zone_configs = [
            ("zone_a", "Excavation Zone A", "excavation"),
            ("zone_b", "Material Storage Zone B", "storage"),
            ("zone_c", "Building Structure Zone C", "structural"),
        ]
        for zid, zname, ztype in zone_configs:
            db.add(Zone(id=zid, site_id=site_id, name=zname, zone_type=ztype, status="active"))
        db.commit()

    result = run_analysis(db, site_id=site_id)
    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))

    return {
        "status": "success",
        "analysis_id": result["analysis_id"],
        "risk_score": result.get("risk", {}).get("overall_score", 0),
        "risk_level": result.get("risk", {}).get("risk_level", "LOW"),
        "safety_score": result.get("safety", {}).get("overall_safety_score", 0),
        "safety_level": result.get("safety", {}).get("overall_safety_level", "LOW"),
        "hazards_count": len(result.get("hazards", [])),
        "recommendations_count": len(result.get("recommendations", [])),
        "worker_count": result.get("worker_count", 0),
        "vehicle_count": result.get("vehicle_count", 0),
        "ppe_compliance": result.get("ppe", {}).get("compliance", 0),
        "video": result.get("video", {}),
        "evidence_note": result.get("evidence_note", ""),
        "timestamp": result.get("timestamp"),
    }


@router.post("/demo/reset")
def reset_demo_data(db: Session = Depends(get_db)):
    from app.models.models import (
        VideoAnalysis, Recommendation, RiskAssessment, RiskAssessmentHazard,
        Hazard, MonitoringEvent, Equipment, Zone, Site, Project, Worker,
        SafetyViolation, SafetyAlert, SafetyAssessment,
    )

    db.query(RiskAssessmentHazard).delete()
    db.query(Recommendation).delete()
    db.query(RiskAssessment).delete()
    db.query(Hazard).delete()
    db.query(MonitoringEvent).delete()
    db.query(Equipment).delete()
    db.query(Worker).delete()
    db.query(SafetyViolation).delete()
    db.query(SafetyAlert).delete()
    db.query(SafetyAssessment).delete()
    db.query(VideoAnalysis).delete()
    db.query(Zone).delete()
    db.query(Site).delete()
    db.query(Project).delete()
    db.commit()
    return {"status": "reset"}


@router.get("/demo/environmental")
def get_environmental_demo(site_id: str = "site_riverside_main", db: Session = Depends(get_db)):
    """Environmental dimensions as supported by the latest video evidence."""
    analysis = get_latest_analysis(db, site_id)
    if not analysis:
        return {
            "available": False,
            "evidence_note": "No video analysis yet. Run Analyze Video first.",
        }
    payload = build_analysis_response(db, analysis)
    risk = payload.get("risk", {}) or {}
    return {
        "available": True,
        "analysis_id": payload.get("analysis_id"),
        "evidence_note": payload.get("evidence_note", ""),
        "lighting_condition": payload.get("video", {}).get("lighting_condition", ""),
        "environmental_score": risk.get("environmental_score", 0),
        "environmental_factors": risk.get("environmental_factors", []),
        "weather_temperature_wind_ground": "Not available from video evidence",
    }


@router.get("/demo/equipment")
def get_equipment_demo(site_id: str = "site_riverside_main", db: Session = Depends(get_db)):
    analysis = get_latest_analysis(db, site_id)
    if not analysis:
        return {"available": False, "equipment": []}
    payload = build_analysis_response(db, analysis)
    return {
        "available": True,
        "analysis_id": payload.get("analysis_id"),
        "equipment": payload.get("equipment", []),
        "count": len(payload.get("equipment", [])),
        "evidence_note": "Equipment is derived only from objects detected in the video.",
    }


@router.get("/demo/scenario")
def get_demo_scenario(site_id: str = "site_riverside_main", db: Session = Depends(get_db)):
    """Latest-analysis summary (replaces the old fabricated risk scenario)."""
    analysis = get_latest_analysis(db, site_id)
    if not analysis:
        return {"scenario": "No analysis yet. Run video analysis to populate the dashboard."}
    payload = build_analysis_response(db, analysis)
    risk = payload.get("risk", {}) or {}
    safety = payload.get("safety", {}) or {}
    return {
        "analysis_id": payload.get("analysis_id"),
        "scenario": risk.get("summary", ""),
        "risk_level": risk.get("risk_level", "LOW"),
        "risk_score": risk.get("overall_score", 0),
        "safety_level": safety.get("overall_safety_level", "LOW"),
        "safety_score": safety.get("overall_safety_score", 0),
        "hazards_count": len(payload.get("hazards", [])),
        "worker_count": payload.get("worker_count", 0),
        "ppe_compliance": payload.get("ppe", {}).get("compliance", 0),
        "evidence_note": payload.get("evidence_note", ""),
    }