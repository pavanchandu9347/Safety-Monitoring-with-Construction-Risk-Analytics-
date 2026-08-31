"""Seed the database with demo data on first startup."""

from datetime import datetime, timezone
from app.database.database import SessionLocal
from app.models.models import Project, Site, Zone, Equipment, MonitoringEvent


def seed_demo_data():
    db = SessionLocal()
    try:
        existing = db.query(Project).first()
        if existing:
            return

        project = Project(
            id="proj_riverside_001",
            name="Riverside Tower Complex",
            description="Mixed-use high-rise development with residential and commercial spaces",
            location="123 Riverside Drive, Metro City",
            status="active",
        )
        db.add(project)

        site = Site(
            id="site_riverside_main",
            project_id="proj_riverside_001",
            name="Riverside Tower Main Site",
            description="Primary construction site for tower complex",
            status="active",
        )
        db.add(site)

        zones = [
            Zone(
                id="zone_a",
                site_id="site_riverside_main",
                name="Excavation Zone A",
                zone_type="excavation",
                status="active",
                risk_level="HIGH",
                current_risk_score=62.0,
            ),
            Zone(
                id="zone_b",
                site_id="site_riverside_main",
                name="Material Storage Zone B",
                zone_type="storage",
                status="active",
                risk_level="LOW",
                current_risk_score=18.0,
            ),
            Zone(
                id="zone_c",
                site_id="site_riverside_main",
                name="Building Structure Zone C",
                zone_type="structural",
                status="active",
                risk_level="MEDIUM",
                current_risk_score=45.0,
            ),
        ]
        db.add_all(zones)

        equipment = [
            Equipment(
                id="eq_excavator_01",
                site_id="site_riverside_main",
                name="Excavator-01",
                equipment_type="excavator",
                status="active",
                zone_id="zone_a",
                activity="excavation",
                operating_duration_minutes=240,
                maintenance_status="operational",
                nearby_worker_count=3,
            ),
            Equipment(
                id="eq_dump_truck_01",
                site_id="site_riverside_main",
                name="Dump Truck-01",
                equipment_type="dump_truck",
                status="active",
                zone_id="zone_a",
                activity="hauling",
                operating_duration_minutes=180,
                maintenance_status="operational",
                nearby_worker_count=1,
            ),
            Equipment(
                id="eq_crane_01",
                site_id="site_riverside_main",
                name="Crane-01",
                equipment_type="crane",
                status="active",
                zone_id="zone_c",
                activity="lifting",
                operating_duration_minutes=300,
                maintenance_status="due_soon",
                nearby_worker_count=5,
            ),
            Equipment(
                id="eq_bulldozer_01",
                site_id="site_riverside_main",
                name="Bulldozer-01",
                equipment_type="bulldozer",
                status="idle",
                zone_id="zone_a",
                activity="idle",
                operating_duration_minutes=60,
                maintenance_status="operational",
                nearby_worker_count=0,
            ),
            Equipment(
                id="eq_mixer_01",
                site_id="site_riverside_main",
                name="Cement Mixer-01",
                equipment_type="cement_mixer",
                status="active",
                zone_id="zone_c",
                activity="mixing",
                operating_duration_minutes=120,
                maintenance_status="overdue",
                nearby_worker_count=2,
            ),
        ]
        db.add_all(equipment)

        now = datetime.now(timezone.utc)
        event = MonitoringEvent(
            id="evt_demo_001",
            site_id="site_riverside_main",
            zone_id="zone_a",
            event_type="construction_activity",
            source="demo_simulation",
            detected_objects=[
                {"label": "person", "confidence": 0.89, "count": 3, "class_id": 0},
                {"label": "excavator", "confidence": 0.92, "count": 1, "class_id": 7},
                {"label": "truck", "confidence": 0.85, "count": 1, "class_id": 7},
            ],
            equipment_activity={
                "excavator_01": {"status": "active", "activity": "excavation"},
                "dump_truck_01": {"status": "active", "activity": "hauling"},
            },
            environmental_conditions={
                "weather": "Rainy",
                "visibility": "Poor",
                "temperature_celsius": 18,
                "humidity_percent": 85,
                "wind_speed_kmh": 32,
            },
            site_conditions={
                "ground_condition": "Wet",
                "lighting_condition": "Adequate",
            },
            description="Active excavation with heavy equipment in poor weather conditions",
            timestamp=now,
        )
        db.add(event)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Seed data error: {e}")
    finally:
        db.close()
