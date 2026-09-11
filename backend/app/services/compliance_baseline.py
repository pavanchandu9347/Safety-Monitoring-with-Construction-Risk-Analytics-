"""Reference regulatory baseline for a construction site (Milestone 3).

This module holds the *requirements* and *required inspections* a site is
measured against, expressed as generic construction-safety standards (in the
spirit of OSHA 29 CFR 1926). These are reference data, NOT results:

* ``ComplianceRequirement.status`` is recomputed from real evidence on every
  analysis by the Compliance Agent. Nothing here is a compliance verdict.
* ``InspectionRecord.status`` defaults to ``NOT_AVAILABLE`` and stays that way
  unless a real inspection record is provided. No completion is ever invented.

Call ``pillars(site_id)`` to get the two dict lists the agent consumes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.models import ComplianceRequirement, InspectionRecord

# ── Default regulatory requirements (reference data) ─────────────────────────

DEFAULT_REQUIREMENTS: List[Dict[str, Any]] = [
    {
        "category": "PPE",
        "requirement": "Required head protection (helmet)",
        "description": "All workers on site shall wear approved head protection.",
        "severity": "HIGH",
        "source": "regulatory_standard",
    },
    {
        "category": "PPE",
        "requirement": "High-visibility safety vest",
        "description": "Workers in active work areas shall wear high-visibility vests.",
        "severity": "HIGH",
        "source": "regulatory_standard",
    },
    {
        "category": "PPE",
        "requirement": "Hand protection (gloves)",
        "description": "Workers handling materials/equipment shall wear hand protection.",
        "severity": "MEDIUM",
        "source": "regulatory_standard",
    },
    {
        "category": "PPE",
        "requirement": "Foot protection (safety boots)",
        "description": "Workers on site shall wear protective footwear.",
        "severity": "MEDIUM",
        "source": "regulatory_standard",
    },
    {
        "category": "Worker Safety",
        "requirement": "Safe worker–equipment separation",
        "description": "Workers shall not remain inside the operating swing/radius of active equipment.",
        "severity": "HIGH",
        "source": "regulatory_standard",
    },
    {
        "category": "Worker Safety",
        "requirement": "Control of unsafe worker behavior",
        "description": "Unsafe behaviors (unauthorized zones, proximity, hazardous actions) shall be controlled.",
        "severity": "HIGH",
        "source": "regulatory_standard",
    },
    {
        "category": "Equipment Safety",
        "requirement": "Equipment operating within assigned zones",
        "description": "Heavy equipment shall operate inside designated/authorized zones.",
        "severity": "HIGH",
        "source": "regulatory_standard",
    },
    {
        "category": "Equipment Safety",
        "requirement": "No worker congestion around active equipment",
        "description": "Avoid concentration of workers in the immediate vicinity of operating equipment.",
        "severity": "HIGH",
        "source": "regulatory_standard",
    },
    {
        "category": "Site Safety",
        "requirement": "Adequate site lighting",
        "description": "Work areas shall maintain adequate illumination for safe operations.",
        "severity": "MEDIUM",
        "source": "regulatory_standard",
    },
    {
        "category": "Site Safety",
        "requirement": "Control of accident-prone zones",
        "description": "Areas with high accident risk shall be identified and controlled.",
        "severity": "HIGH",
        "source": "regulatory_standard",
    },
    {
        "category": "Emergency Preparedness",
        "requirement": "Emergency equipment & egress verified",
        "description": "Emergency equipment and clear egress routes shall be present and verified.",
        "severity": "HIGH",
        "source": "documentation_required",
    },
    {
        "category": "Inspection",
        "requirement": "Statutory inspections performed",
        "description": "Required equipment/site inspections shall be performed and documented.",
        "severity": "HIGH",
        "source": "documentation_required",
    },
    {
        "category": "Environmental",
        "requirement": "Environmental impact monitoring",
        "description": "Environmental monitoring (noise/dust) shall be carried out per permit.",
        "severity": "MEDIUM",
        "source": "documentation_required",
    },
    {
        "category": "Documentation",
        "requirement": "Operator training records",
        "description": "Equipment operators shall hold valid training records/credentials.",
        "severity": "HIGH",
        "source": "documentation_required",
    },
    {
        "category": "Documentation",
        "requirement": "Licenses, certificates & insurance validity",
        "description": "Site licenses, certificates and insurance policies shall be current.",
        "severity": "HIGH",
        "source": "documentation_required",
    },
]

# ── Default required inspections (reference scheduling, no fake completions) ─

def _default_inspections() -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    return [
        {
            "inspection_type": "Daily site walkthrough",
            "description": "Routine daily inspection of site conditions and housekeeping.",
            "due_date": now - timedelta(days=1),     # overdue: no record exists
            "last_inspection": None,
        },
        {
            "inspection_type": "Weekly equipment inspection",
            "description": "Weekly inspection of operating equipment condition.",
            "due_date": now + timedelta(days=4),
            "last_inspection": None,
        },
        {
            "inspection_type": "Monthly lifting-appliance inspection",
            "description": "Monthly documented inspection of lifting equipment.",
            "due_date": now + timedelta(days=18),
            "last_inspection": None,
        },
        {
            "inspection_type": "Fire & emergency preparedness check",
            "description": "Quarterly check of emergency equipment, extinguishers and egress.",
            "due_date": now + timedelta(days=40),
            "last_inspection": None,
        },
    ]


def compliance_requirements() -> List[Dict[str, Any]]:
    """Return the reference requirements as plain dicts (no DB side-effects)."""
    return [dict(r) for r in DEFAULT_REQUIREMENTS]


def required_inspections() -> List[Dict[str, Any]]:
    return _default_inspections()


def site_compliance_baseline(db: Session, site_id: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (requirements, inspections) dicts for a site, including ids."""
    req_rows = db.query(ComplianceRequirement).filter(
        ComplianceRequirement.site_id == site_id
    ).all()
    requirements = [{
        "id": r.id,
        "site_id": r.site_id,
        "category": r.category,
        "requirement": r.requirement,
        "description": r.description,
        "severity": r.severity,
        "source": r.source,
        "status": r.status,
    } for r in req_rows]

    insp_rows = db.query(InspectionRecord).filter(
        InspectionRecord.site_id == site_id
    ).all()
    inspections = [{
        "id": i.id,
        "site_id": i.site_id,
        "inspection_type": i.inspection_type,
        "description": i.description,
        "due_date": i.due_date,
        "last_inspection": i.last_inspection,
        "status": i.status,
        "evidence": i.evidence,
    } for i in insp_rows]
    return requirements, inspections


def ensure_compliance_baseline(db: Session, site_id: str) -> int:
    """Idempotently seed the reference requirements + inspections for a site.

    Returns the count of requirements ensured. Safe to call on every request.
    """
    existing = db.query(ComplianceRequirement).filter(
        ComplianceRequirement.site_id == site_id
    ).count()
    if existing == 0:
        for r in DEFAULT_REQUIREMENTS:
            db.add(ComplianceRequirement(
                id=str(uuid.uuid4()),
                site_id=site_id,
                category=r["category"],
                requirement=r["requirement"],
                description=r["description"],
                severity=r["severity"],
                source=r["source"],
                status="NOT_VERIFIED",
            ))

    existing_insp = db.query(InspectionRecord).filter(
        InspectionRecord.site_id == site_id
    ).count()
    if existing_insp == 0:
        for insp in _default_inspections():
            db.add(InspectionRecord(
                id=str(uuid.uuid4()),
                site_id=site_id,
                inspection_type=insp["inspection_type"],
                description=insp["description"],
                due_date=insp["due_date"],
                last_inspection=None,
                status="NOT_AVAILABLE",
                evidence="No inspection record available. The platform does not fabricate completed inspections.",
            ))
        db.commit()

    return existing if existing else len(DEFAULT_REQUIREMENTS)