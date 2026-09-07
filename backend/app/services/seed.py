"""Seed the database with the reference project/site/zone scaffold on first
startup. Analysis rows (equipment, workers, events, hazards, …) are NO longer
seeded: they are produced solely by the unified video-analysis pipeline.
"""

from app.database.database import SessionLocal
from app.models.models import (
    Project, Site, Zone,
)


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
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Seed data error: {e}")
    finally:
        db.close()
