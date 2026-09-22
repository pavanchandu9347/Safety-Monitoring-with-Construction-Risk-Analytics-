import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database.database import get_db
from app.models.models import (
    Site, Zone, MonitoringEvent, Hazard, RiskAssessment, Recommendation, Equipment
)
from app.schemas.schemas import (
    DashboardResponse, RiskAssessmentResponse, HazardResponse,
    MonitoringEventResponse, EquipmentResponse, ZoneRiskSummary, RiskTrendPoint
)

router = APIRouter()


@router.get("/sites/{site_id}/dashboard", response_model=DashboardResponse)
def get_dashboard(site_id: str, db: Session = Depends(get_db)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    zones = db.query(Zone).filter(Zone.site_id == site_id).all()

    latest_risk = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.site_id == site_id)
        .order_by(RiskAssessment.timestamp.desc())
        .first()
    )

    active_hazards = (
        db.query(Hazard)
        .filter(Hazard.site_id == site_id, Hazard.status != "resolved")
        .order_by(Hazard.timestamp.desc())
        .limit(20)
        .all()
    )

    recent_events = (
        db.query(MonitoringEvent)
        .filter(MonitoringEvent.site_id == site_id)
        .order_by(MonitoringEvent.timestamp.desc())
        .limit(20)
        .all()
    )

    equipment_list = (
        db.query(Equipment)
        .filter(Equipment.site_id == site_id)
        .all()
    )

    risk_history = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.site_id == site_id)
        .order_by(RiskAssessment.timestamp.desc())
        .limit(20)
        .all()
    )

    total_hazards = db.query(Hazard).filter(Hazard.site_id == site_id).count()
    open_hazards = db.query(Hazard).filter(
        Hazard.site_id == site_id, Hazard.status != "resolved"
    ).count()
    critical_hazards = db.query(Hazard).filter(
        Hazard.site_id == site_id, Hazard.severity == "CRITICAL", Hazard.status != "resolved"
    ).count()

    total_recs = db.query(Recommendation).filter(Recommendation.site_id == site_id).count()
    unresolved_recs = db.query(Recommendation).filter(
        Recommendation.site_id == site_id, Recommendation.status == "pending"
    ).count()

    # Per-zone rollups in three aggregate queries (was N+1: one query per zone
    # per metric). Cheap SELECTs executed against the same filters as before.
    zone_ids = [z.id for z in zones]
    zone_hazard_counts: dict = {}
    zone_active_counts: dict = {}
    zone_event_counts: dict = {}
    if zone_ids:
        for zone_id, n in (
            db.query(Hazard.zone_id, func.count())
            .filter(Hazard.zone_id.in_(zone_ids))
            .group_by(Hazard.zone_id)
            .all()
        ):
            zone_hazard_counts[zone_id] = n
        for zone_id, n in (
            db.query(Hazard.zone_id, func.count())
            .filter(Hazard.zone_id.in_(zone_ids), Hazard.status != "resolved")
            .group_by(Hazard.zone_id)
            .all()
        ):
            zone_active_counts[zone_id] = n
        for zone_id, n in (
            db.query(MonitoringEvent.zone_id, func.count())
            .filter(MonitoringEvent.zone_id.in_(zone_ids))
            .group_by(MonitoringEvent.zone_id)
            .all()
        ):
            zone_event_counts[zone_id] = n

    zone_summaries = []
    for zone in zones:
        zone_summaries.append(ZoneRiskSummary(
            zone_id=zone.id,
            zone_name=zone.name,
            zone_type=zone.zone_type,
            risk_score=zone.current_risk_score,
            risk_level=zone.risk_level,
            hazard_count=zone_hazard_counts.get(zone.id, 0),
            active_hazard_count=zone_active_counts.get(zone.id, 0),
            event_count=zone_event_counts.get(zone.id, 0),
        ))

    trend = [
        RiskTrendPoint(timestamp=a.timestamp, score=a.overall_score, risk_level=a.risk_level)
        for a in reversed(risk_history)
    ]

    return DashboardResponse(
        site_id=site_id,
        site_name=site.name,
        generated_at=datetime.now(timezone.utc),
        current_risk_assessment=RiskAssessmentResponse.model_validate(latest_risk) if latest_risk else None,
        active_hazards=[HazardResponse.model_validate(h) for h in active_hazards],
        recent_monitoring_events=[MonitoringEventResponse.model_validate(e) for e in recent_events],
        equipment=[EquipmentResponse.model_validate(eq) for eq in equipment_list],
        zone_risk_data=zone_summaries,
        risk_trend=trend,
        total_hazards=total_hazards,
        open_hazards=open_hazards,
        critical_hazards=critical_hazards,
        total_recommendations=total_recs,
        unresolved_recommendations=unresolved_recs,
    )
