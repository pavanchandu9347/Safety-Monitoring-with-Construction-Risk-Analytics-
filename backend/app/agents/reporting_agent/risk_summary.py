"""Risk summary section for the Reporting Agent (Milestone 4)."""

from __future__ import annotations

from typing import Any, Optional


def build(ctx: dict) -> dict:
    overall = ctx.get("overall_risk") or {}
    score = overall.get("score")
    level = overall.get("level") or "NOT_AVAILABLE"
    summary_text = (overall.get("summary") or "").strip()

    if score is None:
        return {
            "status": "NOT_AVAILABLE",
            "overall_score": None,
            "risk_level": "NOT_AVAILABLE",
            "summary": "Risk intelligence unavailable for this analysis.",
            "components": [],
        }

    components = []
    for key, label in (
        ("environmental_score", "ENVIRONMENTAL"),
        ("equipment_score", "EQUIPMENT"),
        ("site_condition_score", "SITE CONDITION"),
        ("activity_score", "ACTIVITY"),
    ):
        components.append(
            {
                "label": label,
                "score": overall.get(key),
                "factors": overall.get(key.replace("_score", "_factors"), []) or [],
            }
        )

    srs = ctx.get("site_risk_summary") or {}
    return {
        "status": "AVAILABLE",
        "overall_score": score,
        "risk_level": level,
        "summary": summary_text or f"Overall risk level {level} (score {score:.0f}).",
        "components": components,
        "empty_components": sum(1 for c in components if not c["factors"]),
        "site_risk": {
            "hazards_total": srs.get("hazards_total", 0),
            "hazards_by_severity": srs.get("hazards_by_severity", {}),
            "unresolved_hazards": srs.get("unresolved_hazards", 0),
            "violation_count": srs.get("violation_count", 0),
            "violations_by_severity": srs.get("violations_by_severity", {}),
            "open_violation_count": srs.get("open_violation_count", 0),
            "alert_count": srs.get("alert_count", 0),
            "alerts_by_severity": srs.get("alerts_by_severity", {}),
        },
    }