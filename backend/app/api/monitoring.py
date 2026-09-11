import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database.database import get_db
from app.models.models import MonitoringEvent, Site, Zone, Manager
from app.auth.deps import require_auth, authorize_site
from app.schemas.schemas import MonitoringEventCreate, MonitoringEventResponse
from app.services.analysis_pipeline import run_analysis, get_latest_analysis, build_analysis_response
from ai.computer_vision.detector import ConstructionSiteDetector
from ai.computer_vision.ppe_detector import get_ppe_detector, PPEModelUnavailable

router = APIRouter()


@router.get("/sites/{site_id}/monitoring", response_model=list[MonitoringEventResponse])
def list_monitoring_events(site_id: str, limit: int = 50, db: Session = Depends(get_db)):
    events = (
        db.query(MonitoringEvent)
        .filter(MonitoringEvent.site_id == site_id)
        .order_by(MonitoringEvent.timestamp.desc())
        .limit(limit)
        .all()
    )
    return events


@router.post("/monitoring/analyze", response_model=MonitoringEventResponse)
def create_monitoring_event(data: MonitoringEventCreate, db: Session = Depends(get_db), manager: Manager = Depends(require_auth)):
    import uuid
    authorize_site(manager, data.site_id)
    event = MonitoringEvent(id=str(uuid.uuid4()), **data.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.post("/monitoring/simulate")
def simulate_monitoring(site_id: str = "site_riverside_main", db: Session = Depends(get_db)):
    """Run the unified video pipeline and return its live-monitoring payload.

    Kept behind the URL the front end already calls, but now produces real
    video-derived monitoring data under one shared ``analysis_id``.
    """
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    result = run_analysis(db, site_id=site_id)
    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))

    return {
        "event_id": result.get("event_id"),
        "analysis_id": result.get("analysis_id"),
        "environmental_data": {
            "evidence_note": result.get("evidence_note", ""),
            "lighting_condition": result.get("video", {}).get("lighting_condition", ""),
        },
        "equipment_data": result.get("equipment", []),
        "detected_objects": result.get("detected_objects", []),
        "worker_count": result.get("worker_count", 0),
        "vehicle_count": result.get("vehicle_count", 0),
        "events": result.get("events", []),
        "timestamp": result.get("timestamp"),
    }


@router.post("/monitoring/process-image")
async def process_image(
    site_id: str = "site_riverside_main",
    zone_id: str = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    import uuid
    import cv2
    import numpy as np

    contents = await file.read()

    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # ── Real base object detection (Milestone 1) ──────────────────────────
    detector = ConstructionSiteDetector()
    detections = detector.detect_from_frame(frame)
    worker_count = detector.count_workers(detections)
    vehicle_count = detector.count_vehicles(detections)

    # ── Real PPE detection (Milestone 2) ──────────────────────────────────
    now = datetime.now(timezone.utc)
    ppe_detector = get_ppe_detector()
    ppe_block: dict
    ppe_error: str | None = None

    try:
        ppe_detector.available  # trigger load; raises if unavailable
        person_dets = [
            {"bbox": list(d["bbox"]), "confidence": d.get("confidence", 0.9)}
            for d in detections
            if d.get("class_id") == 0
        ]
        ppe_workers = ppe_detector.analyze_workers(frame, person_detections=person_dets)
        ppe_detections = ppe_detector.infer(frame)
        model_used = ppe_workers["model_used"]

        safety_result = _run_image_safety(
            db, site_id, ppe_workers["workers"], detections
        )

        ppe_block = {
            "available": True,
            "model_used": model_used,
            "detections": ppe_detections["detections"],
            "image_width": ppe_detections["image_width"],
            "image_height": ppe_detections["image_height"],
            "workers": ppe_workers["workers"],
            "compliant_count": ppe_workers["compliant_count"],
            "non_compliant_count": ppe_workers["non_compliant_count"],
            "compliance_rate": ppe_workers["compliance_rate"],
            "overall_safety_score": safety_result["overall_safety_score"],
            "overall_safety_level": safety_result["overall_safety_level"],
            "violations": safety_result["violations"],
            "alerts": safety_result["alerts"],
            "recommendations": safety_result["recommendations"],
        }
    except PPEModelUnavailable as exc:
        ppe_error = str(exc)
        ppe_block = {
            "available": False,
            "error": ppe_error,
            "workers": [],
            "compliant_count": 0,
            "non_compliant_count": 0,
            "compliance_rate": 1.0,
        }

    event = MonitoringEvent(
        id=str(uuid.uuid4()),
        site_id=site_id,
        zone_id=zone_id,
        event_type="image_analysis",
        source="computer_vision",
        detected_objects=detections,
        equipment_activity={},
        environmental_conditions={},
        site_conditions={},
        description=f"Image analysis: {worker_count} worker(s), {vehicle_count} vehicle(s)",
        timestamp=now,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "event_id": event.id,
        "image_width": int(frame.shape[1]),
        "image_height": int(frame.shape[0]),
        "detections": detections,
        "worker_count": worker_count,
        "vehicle_count": vehicle_count,
        "ppe_compliance": ppe_block,
        "ppe_error": ppe_error,
        "timestamp": now.isoformat(),
    }


def _run_image_safety(
    db: Session, site_id: str, ppe_workers: list, base_detections: list
) -> dict:
    """Run the Safety Agent consuming real, image-derived worker PPE."""
    from app.models.models import Zone, Equipment
    from app.agents.safety_agent.agent import SafetyAgent
    from app.services.safety_alerts import build_safety_alerts

    zones = db.query(Zone).filter(Zone.site_id == site_id).all()
    equipment = db.query(Equipment).filter(Equipment.site_id == site_id).all()

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
            "nearby_worker_count": e.nearby_worker_count,
        }
        for e in equipment
    ]
    site_conditions = {
        "ground_condition": "",
        "lighting_condition": "Image evidence only",
        "evidence_note": "Image analysis; environmental dimensions not available.",
    }

    agent = SafetyAgent()
    result = agent.analyze_site(
        worker_ppe=ppe_workers,
        equipment_data=equipment_data,
        detected_objects=base_detections,
        site_conditions=site_conditions,
        zone_data=zone_data,
        ppe_source="ppe_detection",
    )

    alert_seed = [
        {"status": "open", "severity": v.get("severity", "LOW")}
        for v in result["ppe_compliance"].get("violations", [])
    ] + [
        {"status": "open", "severity": h.get("severity", "LOW")}
        for h in result["hazards"]
    ]
    return {
        "overall_safety_score": result["overall_safety_score"],
        "overall_safety_level": result["overall_safety_level"],
        "violations": result["hazards"],
        "alerts": build_safety_alerts(
            alert_seed,
            result["ppe_compliance"]["compliance_rate"],
            result["overall_safety_level"],
        ),
        "recommendations": result["recommendations"],
    }
