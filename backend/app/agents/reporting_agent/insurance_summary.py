"""Insurance summary section for the Reporting Agent (Milestone 4).

No insurance claim is ever invented — incident/claim figures come only from
persisted InsuranceAssessment / InsuranceIncident / ClaimRecord rows.
"""

from __future__ import annotations

from typing import Any, Optional


def build(ctx: dict) -> dict:
    data = ctx.get("insurance_summary")
    if data is None:
        return {
            "status": "NOT_AVAILABLE",
            "summary": (
                "Insurance intelligence unavailable for this analysis "
                "(no persisted insurance assessment found)."
            ),
        }

    incidents = ctx.get("insurance_incidents") or []
    claims = ctx.get("claim_records") or []
    open_incidents = int(data.get("open_incidents") or 0)

    bullets = []
    if incidents:
        bullets.append(f"{len(incidents)} verified incident(s) on record")
    if claims:
        bullets.append(f"{len(claims)} claim record(s) assembled")
    if open_incidents == 0 and not incidents:
        bullets.append("no verified incidents detected in this analysis")

    return {
        "status": "AVAILABLE",
        "risk_score": data.get("risk_score"),
        "risk_level": data.get("risk_level") or "LOW",
        "exposure": data.get("exposure", {}),
        "claim_risk": data.get("claim_risk", {}),
        "open_incidents": open_incidents,
        "incident_severity": data.get("incident_severity"),
        "verified_incidents": [i.get("incident_type") for i in incidents],
        "claim_records": len(claims),
        "summary": " ".join(bullets) or (
            f"Insurance risk level {data.get('risk_level', 'LOW')} "
            f"(score {float(data.get('risk_score') or 0):.0f})."
        ),
    }