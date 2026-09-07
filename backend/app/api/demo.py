import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid

from app.database.database import get_db
from app.models.models import (
    Project, Site, Zone, Equipment, MonitoringEvent, Hazard, RiskAssessment, Recommendation
)
from app.services.simulated_data import DemoDataGenerator, EnvironmentalSimulator, EquipmentSimulator
from app.agents.site_risk_agent.agent import SiteRiskAgent
from app.services.video_analysis import get_video_report, attach_worker_counts

router = APIRouter()

demo_gen = DemoDataGenerator()
env_sim = EnvironmentalSimulator()
equip_sim = EquipmentSimulator()
agent = SiteRiskAgent()


@router.post("/demo/generate")
def generate_demo_analysis(site_id: str = "site_riverside_main", db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)

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

    existing_zones = db.query(Zone).filter(Zone.site_id == site_id).all()
    if not existing_zones:
        zone_configs = [
            ("zone_a", "Excavation Zone A", "excavation"),
            ("zone_b", "Material Storage Zone B", "storage"),
            ("zone_c", "Building Structure Zone C", "structural"),
        ]
        for zid, zname, ztype in zone_configs:
            db.add(Zone(id=zid, site_id=site_id, name=zname, zone_type=ztype, status="active"))
        db.flush()
        existing_zones = db.query(Zone).filter(Zone.site_id == site_id).all()

    zones = existing_zones

    # Real detections from the SAME configured source video, not constants.
    video_report = get_video_report(site_id=site_id)

    if not db.query(Equipment).filter(Equipment.site_id == site_id).first():
        eq_data = equip_sim.get_equipment_status(dt=now)
        eq_data = attach_worker_counts(eq_data, video_report.get("worker_count", 0))
        zone_map = {"zone_a": "zone_a", "zone_b": "zone_b", "zone_c": "zone_c"}
        for eq_info in eq_data:
            eq_zone = "zone_a" if "Excavator" in eq_info["name"] or "Dump" in eq_info["name"] or "Bulldozer" in eq_info["name"] else "zone_c"
            db.add(Equipment(
                id=str(uuid.uuid4()),
                site_id=site_id,
                name=eq_info["name"],
                equipment_type=eq_info["type"],
                status=eq_info["status"],
                zone_id=eq_zone,
                activity=eq_info["activity"],
                operating_duration_minutes=eq_info["operating_duration_minutes"],
                maintenance_status=eq_info["maintenance_status"],
                nearby_worker_count=eq_info["nearby_worker_count"],
            ))
        db.flush()

    env_conditions = {}
    for zone in zones:
        env_conditions[zone.name] = env_sim.generate_conditions(
            zone_type=zone.zone_type, dt=now
        )

    equipment_data = equip_sim.get_equipment_status(dt=now)
    # Equipment-proximity risk follows the real video worker count.
    equipment_data = attach_worker_counts(
        equipment_data, video_report.get("worker_count", 0)
    )
    detected_objects = video_report.get("detected_objects", [])

    event_data = {
        "detected_objects": detected_objects,
        "worker_count": video_report.get("worker_count", 0),
        "equipment_activity": {
            e["name"]: {"status": e["status"], "activity": e["activity"]}
            for e in equipment_data
        },
    }

    primary_env = env_sim.generate_conditions(zone_type="excavation", dt=now)
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

    for zone in zones:
        zone.current_risk_score = risk_data["overall_score"]
        zone.risk_level = risk_data["risk_level"]

    event = MonitoringEvent(
        id=str(uuid.uuid4()),
        site_id=site_id,
        zone_id=zones[0].id if zones else None,
        event_type="demo_analysis",
        source="demo_simulation",
        detected_objects=event_data["detected_objects"],
        equipment_activity=event_data["equipment_activity"],
        environmental_conditions=primary_env,
        site_conditions=site_conditions,
        description=f"Demo analysis at {now.strftime('%H:%M:%S')}",
        timestamp=now,
    )
    db.add(event)

    hazard_ids = []
    for h_data in result["hazards"]:
        h_id = str(uuid.uuid4())
        severity_map = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH", "critical": "CRITICAL"}
        db.add(Hazard(
            id=h_id,
            site_id=site_id,
            zone_id=None,
            hazard_type=h_data.get("hazard_type", "unknown"),
            description=h_data.get("description", ""),
            severity=severity_map.get(h_data.get("severity", "medium").lower(), "MEDIUM"),
            risk_contribution=h_data.get("risk_contribution", 0),
            evidence=h_data.get("evidence", ""),
            source=h_data.get("source", "site_risk_agent"),
            recommended_mitigation=h_data.get("recommended_mitigation", ""),
            status="detected",
            timestamp=now,
        ))
        hazard_ids.append(h_id)

    for i, rec_data in enumerate(result["recommendations"]):
        db.add(Recommendation(
            id=str(uuid.uuid4()),
            risk_assessment_id=risk_id,
            site_id=site_id,
            title=rec_data.get("title", ""),
            description=rec_data.get("description", ""),
            priority=rec_data.get("priority", "MEDIUM"),
            hazard_type=rec_data.get("hazard_type", ""),
            related_hazard_id=hazard_ids[i] if i < len(hazard_ids) else None,
            status="pending",
            created_at=now,
        ))

    db.commit()

    return {
        "status": "success",
        "risk_score": risk_data["overall_score"],
        "risk_level": risk_data["risk_level"],
        "hazards_count": len(result["hazards"]),
        "recommendations_count": len(result["recommendations"]),
        "environmental_conditions": primary_env,
        "equipment_count": len(equipment_data),
        "timestamp": now.isoformat(),
    }


@router.post("/demo/reset")
def reset_demo_data(db: Session = Depends(get_db)):
    db.query(Recommendation).delete()
    db.query(RiskAssessment).delete()
    db.query(Hazard).delete()
    db.query(MonitoringEvent).delete()
    db.query(Equipment).delete()
    db.query(Zone).delete()
    db.query(Site).delete()
    db.query(Project).delete()
    db.commit()
    return {"status": "reset"}


@router.get("/demo/environmental")
def get_environmental_demo(zone_type: str = "excavation"):
    now = datetime.now(timezone.utc)
    return env_sim.generate_conditions(zone_type=zone_type, dt=now)


@router.get("/demo/equipment")
def get_equipment_demo():
    now = datetime.now(timezone.utc)
    return equip_sim.get_equipment_status(dt=now)


@router.get("/demo/scenario")
def get_demo_scenario():
    return demo_gen.get_risk_scenario()
