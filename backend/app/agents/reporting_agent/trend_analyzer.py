"""Historical trend analysis for reports (Milestone 4).

Direction is derived ONLY from real, stored per-analysis risk scores. With
fewer than two scored analyses the trend is explicitly unavailable.
"""

from __future__ import annotations

from typing import Any, Optional


def direction(history: Optional[dict]) -> str:
    """'improving' | 'worsening' | 'stable' | 'INSUFFICIENT_DATA'."""
    series = (history or {}).get("series") or []
    scored = [s for s in series if s.get("risk_score") is not None]
    if len(scored) < 2:
        return "INSUFFICIENT_DATA"
    latest = scored[-1]["risk_score"]
    previous = scored[-2]["risk_score"]
    delta = float(latest) - float(previous)
    if delta < -0.5:
        return "improving"
    if delta > 0.5:
        return "worsening"
    return "stable"


def summary(history: Optional[dict]) -> str:
    series = (history or {}).get("series") or []
    scored = [s for s in series if s.get("risk_score") is not None]
    if len(scored) < 2:
        return (history or {}).get("message", "Historical trend unavailable.")
    latest = scored[-1]
    previous = scored[-2]
    return (
        f"Risk score moved from {previous['risk_score']:.0f} to "
        f"{latest['risk_score']:.0f} across the last two analyses "
        f"({direction(history).upper()} trend, based on {len(scored)} real analyses)."
    )


def build(history: Optional[dict]) -> dict:
    history = history or {}
    dirn = direction(history)
    return {
        "status": "AVAILABLE" if dirn != "INSUFFICIENT_DATA" else "INSUFFICIENT_DATA",
        "trend_available": dirn != "INSUFFICIENT_DATA",
        "direction": dirn,
        "message": summary(history),
        "analysis_count": len((history or {}).get("series") or []),
    }