"""Safety summary section for the Reporting Agent (Milestone 4)."""

from __future__ import annotations

from typing import Any, Optional


def build(ctx: dict) -> dict:
    safety = ctx.get("safety_summary") or {}
    score = safety.get("overall_safety_score")
    level = safety.get("overall_safety_level") or "NOT_AVAILABLE"

    ppe_rate = safety.get("ppe_compliance_rate")
    violations = int(safety.get("violation_count") or 0)
    alerts = int(safety.get("alert_count") or 0)

    if score is None:
        return {
            "status": "NOT_AVAILABLE",
            "overall_safety_score": None,
            "overall_safety_level": "NOT_AVAILABLE",
            "summary": "Safety intelligence unavailable for this analysis.",
            "ppe": None,
        }

    bullets = []
    if ppe_rate is not None:
        bullets.append(f"PPE compliance observed at {ppe_rate * 100:.0f}%")
    if violations:
        bullets.append(f"{violations} safety violation(s) recorded")
    if alerts:
        bullets.append(f"{alerts} safety alert(s) raised")

    return {
        "status": "AVAILABLE",
        "overall_safety_score": score,
        "overall_safety_level": level,
        "ppe_compliance_rate": ppe_rate,
        "worker_count": safety.get("worker_count"),
        "violation_count": violations,
        "alert_count": alerts,
        "summary": " ".join(bullets) or f"Safety level {level} (score {score:.0f}).",
    }