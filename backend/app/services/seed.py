"""Seed the database with the reference project/site/zone scaffold on first
startup. Analysis rows (equipment, workers, events, hazards, …) are NO longer
seeded: they are produced solely by the unified video-analysis pipeline.
"""

from app.database.database import SessionLocal
from app.models.models import (
    Project, Site, Zone, Manager,
)
from app.auth.security import hash_password, verify_password
from app.config import (
    DEFAULT_MANAGER_USERNAME, DEFAULT_MANAGER_EMAIL, DEFAULT_MANAGER_PASSWORD,
)
import logging
import os

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
    """Create or reconcile the single site manager account.

    Runs on every startup (there is no demo-mode gate: this is the account that
    signs in). Login uses the USERNAME as identifier. An existing manager for
    the default site is reconciled to the configured username/email/password so
    a stale hash never locks an operator out.

    If no password is configured, an existing account keeps its current hash
    and a brand-new account is not created (with a clear log line).
    """
    username = DEFAULT_MANAGER_USERNAME.lower()
    email = DEFAULT_MANAGER_EMAIL.lower()

    existing = (
        db.query(Manager)
        .filter(Manager.username == username)
        .order_by(Manager.id)
        .first()
    )
    if existing is None:
        existing = (
            db.query(Manager)
            .filter(Manager.site_id == "site_riverside_main")
            .order_by(Manager.id)
            .first()
        )

    password = DEFAULT_MANAGER_PASSWORD or None
    if existing:
        if not password:
            logger.warning(
                "DEFAULT_MANAGER_PASSWORD not set — keeping existing password "
                "for manager '%s'.", username,
            )
            return
        changed = []
        if existing.username != username:
            existing.username = username
            changed.append("username")
        if existing.email != email:
            existing.email = email
            changed.append("email")
        if not verify_password(password, existing.password_hash):
            existing.password_hash = hash_password(password)
            changed.append("password")
        if changed:
            logger.info(
                "Reconciled manager account (%s): %s",
                existing.id, ", ".join(changed),
            )
        else:
            logger.info("Manager account '%s' already up to date", username)
        return

    if not password:
        logger.error(
            "DEFAULT_MANAGER_PASSWORD not set — cannot seed manager '%s'. "
            "Set it in backend/.env so the account can be created.", username,
        )
        return

    db.add(Manager(
        id=os.getenv("DEFAULT_MANAGER_ID", "manager_riverside_001"),
        name=os.getenv("DEFAULT_MANAGER_NAME", "Site Manager"),
        username=username,
        email=email,
        password_hash=hash_password(password),
        role="manager",
        site_id="site_riverside_main",
        is_active=1,
    ))
    logger.info("Seeded manager account: %s", username)
