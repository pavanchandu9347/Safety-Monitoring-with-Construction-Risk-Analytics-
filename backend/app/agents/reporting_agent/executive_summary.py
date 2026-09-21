"""Executive summary for the Reporting Agent (Milestone 4).

Every assertion is derived from the unified intelligence context; trend
direction comes from real historical analyses only.
"""

from __future__ import annotations

from typing import Any, Optional

from app.agents.reporting_agent import trend_analyzer


def _strengths(ctx: dict) -> list[str]:
    out = []
    overall = ctx.get("overall_risk") or {}
    safety = ctx.get("safety_summary") or {}
    compliance = ctx.get("compliance_summary") or {}

    if (overall.get("score") or 0) <= 30 and overall.get("score") is not None:
        out.append(f"Overall risk score is low ({overall['score']:.0f}).")
    ppe_rate = safety.get("ppe_compliance_rate")
    if ppe_rate is not None and ppe_rate >= 0.90:
        out.append(f"PPE compliance observed at {ppe_rate * 100:.0f}%.")
    if not ctx.get("critical_findings"):
        out.append("No critical findings in this analysis.")
    if not ctx.get("open_violations"):
        out.append("No open safety violations.")
    if compliance and compliance.get("compliance_level", "").upper() == "COMPLIANT":
        out.append("Compliance assessment is fully compliant.")
    return out


def _concerns(ctx: dict) -> list[str]:
    out = []
    critical = ctx.get("critical_findings") or []
    high = ctx.get("high_findings") or []
    for f in critical:
        out.append(f"[CRITICAL] {f.get('title', '')}")
    for f in high:
        out.append(f"[HIGH] {f.get('title', '')}")
    if not out:
        return ["No high or critical findings in this analysis."]
    return out


def build(ctx: dict, history: Optional[dict] = None) -> dict:
    overall = ctx.get("overall_risk") or {}
    score = overall.get("score")
    level = overall.get("level") or "NOT_AVAILABLE"
    dirn = trend_analyzer.direction(history)

    response_bits = []
    if score is not None:
        response_bits.append(f"Overall site risk is assessed at {level} (score {score:.0f}).")
    else:
        response_bits.append("No risk assessment result is available for this analysis.")

    trend_note = ""
    if dirn != "INSUFFICIENT_DATA":
        trend_msg = trend_analyzer.summary(history)
        response_bits.append(trend_msg)
        trend_note = trend_msg

    concerns = _concerns(ctx)
    if any(c.startswith("[CRITICAL]") for c in concerns):
        response_bits.append(
            "Immediate attention is required for the critical finding(s) listed below."
        )

    strengths = _strengths(ctx)
    if strengths:
        response_bits.append("Observed strengths: " + " ".join(strengths))

    short_line = response_bits[0] if response_bits else "No intelligence available."

    return {
        "overall_risk_level": level,
        "overall_risk_score": score,
        "risk_trend_direction": dirn,
        "trend_note": trend_note,
        "key_concerns": concerns,
        "key_strengths": strengths,
        "response": " ".join(response_bits),
        "short_line": short_line,
    }