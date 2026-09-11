"""Claim documentation.

A claim dossier is ONLY produced for real, verified incidents. When no
incident exists, the module returns an explicit "no claim documentation"
status instead of inventing documents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _document(incident: Dict[str, Any], severity: Dict[str, Any], index: int) -> Dict[str, Any]:
    return {
        "document_id": f"CLAIM-{str(incident.get('analysis_id', 'ANALYSIS'))[:8]}-{index + 1}",
        "incident_type": incident.get("incident_type"),
        "incident_date": _iso(incident.get("timestamp")),
        "severity": severity.get("severity_level"),
        "severity_score": severity.get("severity_score"),
        "description": incident.get("description"),
        "workers_involved": incident.get("affected_workers") or 0,
        "equipment_involved": incident.get("equipment_involved"),
        "location": incident.get("location"),
        "evidence": [
            {k: _iso(v) for k, v in e.items()} if isinstance(e, dict) else e
            for e in (incident.get("evidence") or [])
        ],
        "status": "DRAFTED",  # Docs are drafted when evidence supports them.
    }


def _reference(level: str) -> str:
    return {
        "LOW": "No action immediately required.",
        "MEDIUM": "Retain records; monitoring recommended.",
        "HIGH": "Notify site management; prepare supporting records.",
        "CRITICAL": "Escalate; prepare claim submission records.",
    }.get(level, "")


def build(
    incidents: list,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    documents: list = []
    for i, inc in enumerate(incidents):
        documents.append(_document(inc, inc.get("severity_details") or {}, i))

    if not documents:
        return {
            "status": "NO_CLAIM_DOCUMENTATION",
            "reason": "No verified insurance incidents in this analysis.",
            "documents": [],
            "count": 0,
        }

    peak = max(
        (str(i.get("severity_details", {}).get("severity_level", "LOW")).upper()
         for i in incidents),
        default="LOW",
    )
    return {
        "status": "AVAILABLE",
        "documents": documents,
        "count": len(documents),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reference": _reference(peak),
    }