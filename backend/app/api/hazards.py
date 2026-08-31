from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.models import Hazard
from app.schemas.schemas import HazardResponse

router = APIRouter()


@router.get("/sites/{site_id}/hazards", response_model=list[HazardResponse])
def list_hazards(
    site_id: str,
    severity: str = None,
    status: str = None,
    zone_id: str = None,
    db: Session = Depends(get_db),
):
    query = db.query(Hazard).filter(Hazard.site_id == site_id)
    if severity:
        query = query.filter(Hazard.severity == severity.upper())
    if status:
        query = query.filter(Hazard.status == status)
    if zone_id:
        query = query.filter(Hazard.zone_id == zone_id)
    return query.order_by(Hazard.timestamp.desc()).all()


@router.get("/hazards/{hazard_id}", response_model=HazardResponse)
def get_hazard(hazard_id: str, db: Session = Depends(get_db)):
    hazard = db.query(Hazard).filter(Hazard.id == hazard_id).first()
    if not hazard:
        raise HTTPException(status_code=404, detail="Hazard not found")
    return hazard


@router.patch("/hazards/{hazard_id}/status")
def update_hazard_status(hazard_id: str, new_status: str, db: Session = Depends(get_db)):
    hazard = db.query(Hazard).filter(Hazard.id == hazard_id).first()
    if not hazard:
        raise HTTPException(status_code=404, detail="Hazard not found")
    if new_status not in ("detected", "investigating", "mitigated", "resolved"):
        raise HTTPException(status_code=400, detail="Invalid status")
    hazard.status = new_status
    if new_status == "resolved":
        from datetime import datetime, timezone
        hazard.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return {"hazard_id": hazard_id, "status": new_status}
