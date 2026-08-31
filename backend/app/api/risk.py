import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database.database import get_db
from app.models.models import RiskAssessment, Recommendation, Site, Zone, Hazard
from app.schemas.schemas import RiskAssessmentResponse, RecommendationResponse, RiskTrendPoint
from app.agents.site_risk_agent.agent import SiteRiskAgent
from app.services.simulated_data import EnvironmentalSimulator, EquipmentSimulator, DemoDataGenerator

router = APIRouter()

agent = SiteRiskAgent()
env_sim = EnvironmentalSimulator()
equip_sim = EquipmentSimulator()
demo_gen = DemoDataGenerator()


@router.get("/sites/{site_id}/risk", response_model=RiskAssessmentResponse)
def get_current_risk(site_id: str, db: Session = Depends(get_db)):
    risk = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.site_id == site_id)
        .order_by(RiskAssessment.timestamp.desc())
        .first()
    )
    if not risk:
        return run_risk_analysis(site_id, db)
    return risk


@router.get("/sites/{site_id}/risk/history", response_model=list[RiskTrendPoint])
def get_risk_history(site_id: str, limit: int = 50, db: Session = Depends(get_db)):
    assessments = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.site_id == site_id)
        .order_by(RiskAssessment.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        RiskTrendPoint(timestamp=a.timestamp, score=a.overall_score, risk_level=a.risk_level)
        for a in reversed(assessments)
    ]


@router.get("/sites/{site_id}/recommendations", response_model=list[RecommendationResponse])
def get_recommendations(site_id: str, db: Session = Depends(get_db)):
    return (
        db.query(Recommendation)
        .filter(Recommendation.site_id == site_id)
        .order_by(Recommendation.created_at.desc())
        .all()
    )


@router.post("/sites/{site_id}/risk/analyze")
def run_risk_analysis(site_id: str, db: Session = Depends(get_db)) -> dict:
    import uuid

    now = datetime.now(timezone.utc)

    zones = db.query(Zone).filter(Zone.site_id == site_id).all()
    zone_names = [z.name for z in zones]
    zone_types = [z.zone_type for z in zones]

    env_data = {}
    for zone in zones:
        env_data[zone.name] = env_sim.generate_conditions(
            zone_type=zone.zone_type, dt=now
        )

    equipment_data = equip_sim.get_equipment_status(dt=now)

    event_data = {
        "detected_objects": [
            {"label": "person", "confidence": 0.88, "count": 3, "class_id": 0},
            {"label": "excavator", "confidence": 0.91, "count": 1, "class_id": 7},
            {"label": "truck", "confidence": 0.85, "count": 1, "class_id": 7},
        ],
        "equipment_activity": {
            e["name"]: {"status": e["status"], "activity": e["activity"]}
            for e in equipment_data
        },
    }

    primary_env = env_data.get(zone_names[0], env_sim.generate_conditions(dt=now))
    site_conditions = {
        "ground_condition": primary_env.get("ground_condition", "Dry"),
        "lighting_condition": primary_env.get("lighting_condition", "Good"),
    }

    result = agent.analyze_site(
        event_data=event_data,
        equipment_data=equipment_data,
        environmental_data=primary_env,
        site_conditions=site_conditions,
        detected_objects=event_data["detected_objects"],
    )

    risk_data = result["risk_assessment"]
    risk_id = str(uuid.uuid4())
    risk_assessment = RiskAssessment(
        id=risk_id,
        site_id=site_id,
        timestamp=now,
        overall_score=risk_data["overall_score"],
        risk_level=risk_data["risk_level"],
        environmental_score=risk_data["environmental_score"],
        equipment_score=risk_data["equipment_score"],
        site_condition_score=risk_data["site_condition_score"],
        activity_score=risk_data["activity_score"],
        environmental_factors=risk_data["environmental_factors"],
        equipment_factors=risk_data["equipment_factors"],
        site_condition_factors=risk_data["site_condition_factors"],
        activity_factors=risk_data["activity_factors"],
        summary=risk_data["summary"],
    )
    db.add(risk_assessment)

    for hazard_data in result["hazards"]:
        hazard_id = str(uuid.uuid4())
        severity_map = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH", "critical": "CRITICAL"}
        severity = severity_map.get(
            hazard_data.get("severity", "medium").lower(), "MEDIUM"
        )
        hazard = Hazard(
            id=hazard_id,
            site_id=site_id,
            zone_id=None,
            hazard_type=hazard_data.get("hazard_type", "unknown"),
            description=hazard_data.get("description", ""),
            severity=severity,
            risk_contribution=hazard_data.get("risk_contribution", 0),
            evidence=hazard_data.get("evidence", ""),
            source=hazard_data.get("source", "site_risk_agent"),
            recommended_mitigation=hazard_data.get("recommended_mitigation", ""),
            status="detected",
            timestamp=now,
        )
        db.add(hazard)

        rec_data = next(
            (r for r in result["recommendations"] if r.get("related_hazard_id") == hazard_data.get("hazard_type")),
            result["recommendations"][0] if result["recommendations"] else None,
        )
        if rec_data:
            rec = Recommendation(
                id=str(uuid.uuid4()),
                risk_assessment_id=risk_id,
                site_id=site_id,
                title=rec_data.get("title", ""),
                description=rec_data.get("description", ""),
                priority=rec_data.get("priority", "MEDIUM"),
                hazard_type=rec_data.get("hazard_type", ""),
                related_hazard_id=hazard_id,
                status="pending",
                created_at=now,
            )
            db.add(rec)

    for zone in zones:
        zone.current_risk_score = risk_data["overall_score"]
        zone.risk_level = risk_data["risk_level"]
    db.commit()

    return {
        "risk_assessment": RiskAssessmentResponse.model_validate(risk_assessment).model_dump(),
        "hazards_count": len(result["hazards"]),
        "recommendations_count": len(result["recommendations"]),
    }
