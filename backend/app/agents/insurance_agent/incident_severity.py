"""Incident severity classification.

Incidents are ONLY derived from real evidence (HIGH/CRITICAL hazards or a
CRITICAL safety alert). This module classifies each incident's severity from
its actual attributes — never invents incidents.
"""

from __future__ import annotations

from typing import Any, Dict

LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def _score_to_level(score: float) -> str:
    if score < 25:
        return "LOW"
    if score < 50:
        return "MEDIUM"
    if score < 75:
        return "HIGH"
    return "CRITICAL"


def classify(
    incident: Dict[str, Any],
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Compute severity for one real incident from its evidence attributes."""

    hazard_severity = str(incident.get("severity", "MEDIUM")).upper()
    severity_score = {"LOW": 15, "MEDIUM": 35, "HIGH": 60, "CRITICAL": 85}.get(
        hazard_severity, 30
    )

    affected = int(incident.get("affected_workers", 0) or 0)
    if affected > 1:
        severity_score += 15
    elif affected == 1:
        severity_score += 5

    if incident.get("equipment_involved"):
        severity_score += 10
    if incident.get("ppe_violation"):
        severity_score += 15
    if incident.get("location_risk"):
        severity_score += 10
    if incident.get("repeated"):
        severity_score += 10

    score = round(min(severity_score, 100.0), 1)
    return {
        "incident_type": incident.get("incident_type"),
        "severity_score": score,
        "severity_level": _score_to_level(score),
        "factors": {
            "hazard_severity": hazard_severity,
            "affected_workers": affected,
            "equipment_involved": bool(incident.get("equipment_involved")),
            "ppe_violation": bool(incident.get("ppe_violation")),
            "location_risk": bool(incident.get("location_risk")),
            "repeated": bool(incident.get("repeated")),
        },
    }


def aggregate_level(incidents: list) -> str:
    """Overall verified-incident severity across the analysis."""
    if not incidents:
        return "LOW"
    levels = [str(i.get("severity", "LOW")).upper() for i in incidents]
    return max(levels, key=lambda lvl: LEVELS.index(lvl) if lvl in LEVELS else 0)