"""Seed the database with the reference project/site/zone scaffold on first
startup. Analysis rows (equipment, workers, events, hazards, …) are NO longer
seeded: they are produced solely by the unified video-analysis pipeline.
"""

from app.database.database import SessionLocal
from app.models.models import (
    Project, Site, Zone, Manager,
)
from app.auth.security import hash_password, verify_password
from app.config import DEFAULT_MANAGER_EMAIL, DEFAULT_MANAGER_PASSWORD
import logging
import os
import secrets

logger = logging.getLogger(__name__)


def seed_demo_data():
    db = SessionLocal()
    try:
        existing = db.query(Project).first()
        if existing:
            # Scaffold already present; only (idempotent) manager seeding remains.
            seed_manager(db)
            db.commit()
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

        seed_manager(db)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Seed data error: {e}")
    finally:
        db.close()


def seed_manager(db):
    """Upsert the demo manager account so the configured login always works.

    Credentials come from the environment (``DEFAULT_MANAGER_EMAIL`` /
    ``DEFAULT_MANAGER_PASSWORD``). If a manager already exists for the default
    site, its email/password are reconciled to the configured values — this
    keeps an existing (old) account in the database usable with the new
    credentials instead of leaving a stale hash behind.

    If no password is configured a cryptographically random one is generated
    and logged ONCE at startup for a brand-new account; an existing account is
    never overwritten in that case.
    """
    email = DEFAULT_MANAGER_EMAIL.lower()
    existing = (
        db.query(Manager)
        .filter(Manager.site_id == "site_riverside_main")
        .order_by(Manager.id)
        .first()
    )

    password = DEFAULT_MANAGER_PASSWORD or None
    if existing:
        if not password:
            return
        changed = []
        if existing.email != email:
            existing.email = email
            changed.append("email")
        if not verify_password(password, existing.password_hash):
            existing.password_hash = hash_password(password)
            changed.append("password")
        if changed:
            logger.info(
                "Reconciled demo manager account (%s) with configured credentials: %s",
                existing.id, ", ".join(changed),
            )
        return

    if not password:
        password = secrets.token_urlsafe(12)
        logger.warning(
            "DEFAULT_MANAGER_PASSWORD not set — demo manager '%s' created with "
            "random password '%s' (set it in backend/.env to use a custom one).",
            email, password,
        )
    elif password.strip() == "CHANGE-ME-PLEASE":
        logger.warning(
            "Demo manager '%s' uses the placeholder password from .env.example; "
            "set DEFAULT_MANAGER_PASSWORD in backend/.env to a real value "
            "before deploying.", email,
        )

    db.add(Manager(
        id=os.getenv("DEFAULT_MANAGER_ID", "manager_riverside_001"),
        name=os.getenv("DEFAULT_MANAGER_NAME", "Riverside Site Manager"),
        email=email,
        password_hash=hash_password(password),
        role="manager",
        site_id="site_riverside_main",
        is_active=1,
    ))
    logger.info("Seeded demo manager account: %s", email)
