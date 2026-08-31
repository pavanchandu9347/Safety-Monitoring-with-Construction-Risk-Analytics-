import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database.database import get_db
from app.models.models import MonitoringEvent, Site, Zone
from app.schemas.schemas import MonitoringEventCreate, MonitoringEventResponse
from app.services.simulated_data import EnvironmentalSimulator, EquipmentSimulator

router = APIRouter()

env_sim = EnvironmentalSimulator()
equip_sim = EquipmentSimulator()


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
def create_monitoring_event(data: MonitoringEventCreate, db: Session = Depends(get_db)):
    import uuid
    event = MonitoringEvent(id=str(uuid.uuid4()), **data.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.post("/monitoring/simulate")
def simulate_monitoring(site_id: str = "site_riverside_main", db: Session = Depends(get_db)):
    import uuid

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    zones = db.query(Zone).filter(Zone.site_id == site_id).all()
    now = datetime.now(timezone.utc)

    env_conditions = {}
    for zone in zones:
        env_conditions[zone.name] = env_sim.generate_conditions(
            zone_type=zone.zone_type, dt=now
        )

    equipment_data = equip_sim.get_equipment_status(dt=now)

    detected_objects = [
        {"label": "person", "confidence": 0.88, "count": 3, "class_id": 0},
        {"label": "truck", "confidence": 0.85, "count": 1, "class_id": 7},
    ]

    active_equip = {e["name"]: {"status": e["status"], "activity": e["activity"]}
                    for e in equipment_data if e["status"] == "active"}

    first_zone = zones[0] if zones else None
    event = MonitoringEvent(
        id=str(uuid.uuid4()),
        site_id=site_id,
        zone_id=first_zone.id if first_zone else None,
        event_type="simulated_monitoring",
        source="demo_simulation",
        detected_objects=detected_objects,
        equipment_activity=active_equip,
        environmental_conditions=env_conditions,
        site_conditions={"ground_condition": "Wet", "lighting_condition": "Adequate"},
        description=f"Simulated monitoring at {now.strftime('%H:%M:%S')}",
        timestamp=now,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "event_id": event.id,
        "environmental_data": env_conditions,
        "equipment_data": equipment_data,
        "detected_objects": detected_objects,
        "timestamp": now.isoformat(),
    }


@router.post("/monitoring/process-image")
async def process_image(
    site_id: str = "site_riverside_main",
    zone_id: str = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    import uuid
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    from ai.computer_vision.detector import ConstructionSiteDetector

    contents = await file.read()
    import tempfile, cv2
    import numpy as np

    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    detector = ConstructionSiteDetector()
    detections = detector.detect_from_frame(frame)

    worker_count = detector.count_workers(detections)
    vehicle_count = detector.count_vehicles(detections)

    now = datetime.now(timezone.utc)
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
        description=f"Image analysis: {worker_count} workers, {vehicle_count} vehicles detected",
        timestamp=now,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "event_id": event.id,
        "detections": detections,
        "worker_count": worker_count,
        "vehicle_count": vehicle_count,
        "timestamp": now.isoformat(),
    }
