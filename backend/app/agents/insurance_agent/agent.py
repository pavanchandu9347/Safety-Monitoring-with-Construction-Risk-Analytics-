"""Insurance Agent orchestrator (Milestone 3).

Derives real incidents from HIGH/CRITICAL hazards and CRITICAL safety alerts,
classifies their severity, and produces an explainable insurance risk
assessment: exposure by dimension, claim risk, an overall risk score, claim
documentation (only when verified incidents exist) and recommendations.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.insurance_agent.exposure_analyzer import analyze as analyze_exposure
from app.agents.insurance_agent.claim_risk_analyzer import analyze as analyze_claim_risk
from app.agents.insurance_agent.insurance_scorer import compute as score_insurance
from app.agents.insurance_agent.claim_documentation import build as build_doc
from app.agents.insurance_agent.recommendation_engine import generate as generate_recs
from app.agents.insurance_agent.incident_severity import (
    classify as classify_severity,
    aggregate_level,
)

_SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class InsuranceAgent:
    """Main orchestrator for Milestone 3 — insurance risk intelligence."""

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.weights = weights

    def analyze_site(self, context: Dict[str, Any]) -> Dict[str, Any]:
        safety = context.get("safety") or {}
        hazards = list(context.get("hazards") or []) + list(safety.get("hazards") or [])
        alerts = list(context.get("alerts") or [])

        incidents = self._derive_incidents(hazards, alerts, context)
        for incident in incidents:
            incident["severity_details"] = classify_severity(incident, context)

        exposure = analyze_exposure({
            "safety": safety,
            "compliance": context.get("compliance"),
            "worker_ppe": context.get("worker_ppe") or [],
            "hazards": hazards,
            "incidents": incidents,
        })

        claim_risk = analyze_claim_risk(context, incidents, context.get("compliance") or {})

        result = score_insurance(exposure, claim_risk, weights=self.weights)

        documentation = build_doc(incidents, context)

        recommendations = generate_recs(
            exposure, claim_risk, result, context.get("compliance") or {}
        )

        ranking = {"overall": result["risk_level"], "score": result["insurance_risk_score"]}

        summary = self._summary(incidents, exposure, claim_risk, result)

        return {
            "status": self._status(result["risk_level"]),
            "site_id": context.get("site_id"),
            "analysis_id": context.get("analysis_id"),
            "insurance_risk_score": result["insurance_risk_score"],
            "risk_level": result["risk_level"],
            "incidents": incidents,
            "incident_count": len(incidents),
            "incident_severity": aggregate_level(incidents),
            "exposure": exposure,
            "claim_risk": claim_risk,
            "claim_documentation": documentation,
            "evidence_available": bool(
                exposure.get("evidence_available") or claim_risk.get("evidence")
            ),
            "risk_factors": result["factors"],
            "recommendations": recommendations,
            "summary": summary,
            "report": {
                "site_id": context.get("site_id"),
                "analysis_id": context.get("analysis_id"),
                "assessment_date": datetime.now(timezone.utc).isoformat(),
                "insurance_risk_score": result["insurance_risk_score"],
                "risk_level": result["risk_level"],
                "incident_count": len(incidents),
                "exposure": {
                    k: {"score": v["score"], "level": v["level"]}
                    for k, v in exposure.items() if k not in ("overall", "evidence_available")
                },
                "claim_risk": claim_risk,
                "documents": documentation,
                "weighting": result["weights"],
                "evidence": claim_risk.get("evidence", []),
            },
        }

    # ── Private helpers ────────────────────────────────────────────────────

    def _derive_incidents(
        self, hazards: List[Dict[str, Any]], alerts: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        incidents: List[Dict[str, Any]] = []
        worker_ppe = context.get("worker_ppe") or []
        timestamp = context.get("timestamp")

        # Verified high-severity hazards are real incidents.
        severe = [
            h for h in hazards
            if str(h.get("severity", "")).upper() in ("HIGH", "CRITICAL")
        ]
        severe.sort(key=lambda h: _SEVERITY_RANK.get(str(h.get("severity", "")).upper(), 0), reverse=True)
        for hazard in severe:
            hazard_type = str(hazard.get("hazard_type", "hazard")).replace("_", " ").title()
            affected = len([w for w in worker_ppe if w.get("ppe_required", True)])
            incidents.append({
                "incident_type": hazard_type,
                "description": str(hazard.get("description", "")) or f"{hazard_type} detected.",
                "severity": str(hazard.get("severity", "HIGH")).upper(),
                "timestamp": hazard.get("timestamp") or timestamp,
                "analysis_id": context.get("analysis_id"),
                "affected_workers": affected,
                "equipment_involved": bool(
                    hazard.get("equipment_type") or hazard.get("zone_name")
                ),
                "ppe_violation": bool(
                    any(w.get("ppe_required", True) for w in worker_ppe)
                ),
                "location_risk": bool(hazard.get("zone_name") or hazard.get("location")),
                "repeated": hazard.get("repeated", False),
                "location": hazard.get("zone_name") or hazard.get("location"),
                "evidence": [
                    {
                        "kind": "hazard",
                        "hazard_type": hazard.get("hazard_type"),
                        "severity": hazard.get("severity"),
                        "frame": hazard.get("frame"),
                        "frames": hazard.get("frames"),
                        "location": hazard.get("location"),
                        "video_source": hazard.get("video_source"),
                    }
                ],
            })

        # CRITICAL safety alerts are also real incidents.
        for alert in alerts:
            if str(alert.get("severity", "")).upper() != "CRITICAL":
                continue
            alert_type = str(alert.get("alert_type", "safety_alert")).replace("_", " ").title()
            segments = [seg for seg in re.split(r"[.|]", str(alert.get("message", ""))) if seg]
            incidents.append({
                "incident_type": alert_type,
                "description": str(alert.get("message", "")) or f"{alert_type} alert raised.",
                "severity": "CRITICAL",
                "timestamp": alert.get("timestamp") or timestamp,
                "analysis_id": context.get("analysis_id"),
                "affected_workers": alert.get("affected_workers", 1),
                "equipment_involved": bool(alert.get("equipment_type")),
                "ppe_violation": bool(alert.get("ppe_violation", False)),
                "location_risk": bool(alert.get("zone_name") or alert.get("location")),
                "repeated": len(segments) > 1,
                "location": alert.get("zone_name") or alert.get("location"),
                "evidence": [{
                    "kind": "alert",
                    "alert_type": alert.get("alert_type"),
                    "severity": alert.get("severity"),
                    "frame": alert.get("frame"),
                    "location": alert.get("location"),
                }],
            })

        return incidents

    def _status(self, risk_level: str) -> str:
        return {
            "LOW": "LOW_RISK",
            "MEDIUM": "ELEVATED_RISK",
            "HIGH": "HIGH_RISK",
            "CRITICAL": "CRITICAL_RISK",
        }.get(risk_level, "LOW_RISK")

    def _summary(
        self,
        incidents: List[Dict[str, Any]],
        exposure: Dict[str, Any],
        claim_risk: Dict[str, Any],
        result: Dict[str, Any],
    ) -> str:
        if not incidents and not exposure.get("evidence_available"):
            return (
                "No material insurance exposure identified in this analysis: "
                "no verified incidents, hazards, or PPE violations were detected."
            )
        incident_bit = (
            f"{len(incidents)} verified incident(s)."
            if incidents
            else "No verified incidents."
        )
        overall = exposure.get("overall", {})
        return (
            f"Insurance exposure is {overall.get('level', 'LOW')} "
            f"({overall.get('score', 0)}); {incident_bit} "
            f"Claim risk {claim_risk.get('claim_risk_level', 'LOW')} "
            f"({claim_risk.get('claim_risk_score', 0)}). "
            f"Overall insurance risk {result['risk_level']} "
            f"({result['insurance_risk_score']}/100)."
        )