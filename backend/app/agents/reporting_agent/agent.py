"""Reporting Agent orchestrator (Milestone 4 - Reporting Intelligence).

``ReportingAgent.generate`` consumes the unified intelligence context produced
by the Construction Risk Intelligence Engine (plus optional historical
analytics) and produces the structured report payload that ``report_service``
persists as a ``RiskReport``. It strictly read-models existing data — it never
re-runs models and never invents facts.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from app.agents.reporting_agent import (
    compliance_summary,
    evidence_summary,
    executive_summary,
    insurance_summary,
    recommendation_summary,
    risk_summary,
    safety_summary,
    trend_analyzer,
)

logger = logging.getLogger(__name__)

_ACTION_PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "LOWEST": 4}


def _site_info(ctx: dict) -> dict:
    return {
        "site_id": ctx.get("site_id") or "NOT_AVAILABLE",
        "site_name": ctx.get("site_name") or ctx.get("site_id") or "NOT_AVAILABLE",
    }


def _analysis_info(ctx: dict) -> dict:
    video = (ctx.get("evidence_summary") or {}).get("video") or {}
    result = {
        "analysis_id": ctx.get("analysis_id") or "NOT_AVAILABLE",
        "video_source": video.get("filename") or "NOT_AVAILABLE",
        "frames_analyzed": video.get("frames_analyzed"),
        "model_used": video.get("model_used") or "NOT_AVAILABLE",
    }
    return result


def _limitations(ctx: dict) -> list:
    """Traceable limitations derived from the REAL evidence state — never generic filler."""
    dq = ctx.get("data_quality") or {}
    evidence = ctx.get("evidence_summary") or {}
    video = evidence.get("video") or {}
    overall = ctx.get("overall_risk") or {}

    out: list[str] = []
    status = (dq.get("status") or "NOT_AVAILABLE").upper()
    if status != "COMPLETE":
        out.append(f"Intelligence quality is {status.replace('_', ' ')}.")
    ndims = dq.get("insufficient_dimensions") or []
    if ndims:
        out.append(
            "Insufficient evidence was recorded for: "
            + ", ".join(str(d) for d in ndims)
            + "."
        )
    if overall.get("score") is None:
        out.append("No risk score could be derived for this analysis — nothing was invented.")
    if not video or not video.get("frames_analyzed"):
        out.append("No video-frame evidence was recoverable for this analysis.")
    out.append(
        "All values are derived from persisted analysis results only; "
        "missing evidence is marked NOT_AVAILABLE, never assumed."
    )
    return out


class ReportingAgent:
    """Turn an intelligence context into a structured executive report."""

    def generate(
        self,
        intelligence: dict,
        history: Optional[dict] = None,
        *,
        report_type: str = "risk_intelligence",
    ) -> dict:
        ctx = intelligence or {}
        history = history or {}
        analysis_id = ctx.get("analysis_id")
        site_id = ctx.get("site_id")

        exec_summary = executive_summary.build(ctx, history)

        report = {
            "title": report_type.replace("_", " ").title(),
            "report_type": report_type,
            "analysis_id": analysis_id,
            "site_id": site_id,
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
            "site_info": _site_info(ctx),
            "analysis_info": _analysis_info(ctx),
            "executive_summary": exec_summary,
            "sections": {
                "risk": risk_summary.build(ctx),
                "safety": safety_summary.build(ctx),
                "compliance": compliance_summary.build(ctx),
                "insurance": insurance_summary.build(ctx),
            },
            "critical_findings": ctx.get("critical_findings", []),
            "high_findings": ctx.get("high_findings", []),
            "open_violations": ctx.get("open_violations", []),
            "prioritized_actions": recommendation_summary.prioritized_actions(ctx),
            "historical_analytics": trend_analyzer.build(history),
            "evidence_summary": evidence_summary.build(ctx),
            "data_quality": ctx.get("data_quality", {}),
            "limitations": _limitations(ctx),
        }
        report["summary"] = exec_summary.get("short_line") or (
            "Risk intelligence report generated."
        )
        return report