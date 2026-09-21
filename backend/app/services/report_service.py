"""Report generation & persistence service (Milestone 4 - Reporting Intelligence).

Reports are generated ONLY from persisted analysis results through the shared
intelligence context + Reporting Agent, and each stored ``RiskReport`` always
references the exact ``analysis_id`` it was built from — a report can never
silently combine unrelated analyses.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.reporting_agent import ReportingAgent
from app.models.models import RiskReport, VideoAnalysis
from app.services.historical_analytics import build_history
from app.services.intelligence import (
    AnalysisNotFoundError,
    IntelligenceEngine,
    IntelligenceError,
)

logger = logging.getLogger(__name__)


def _analysis_or_error(db: Session, site_id: str, analysis_id: str) -> VideoAnalysis:
    analysis = (
        db.query(VideoAnalysis)
        .filter(
            VideoAnalysis.id == analysis_id,
            VideoAnalysis.site_id == site_id,
        )
        .first()
    )
    if analysis is None:
        raise AnalysisNotFoundError(
            f"Analysis {analysis_id} not found for site {site_id} — report not generated."
        )
    return analysis


def generate_report(
    db: Session,
    site_id: str,
    analysis_id: str,
    *,
    generated_by: Optional[str] = None,
    report_type: str = "risk_intelligence",
) -> RiskReport:
    """Generate and persist an executive risk report for one real analysis.

    The report is re-derived purely from persisted rows; the shared single
    analysis input keeps every intelligence agent aligned on the same evidence.
    """
    _analysis_or_error(db, site_id, analysis_id)

    intelligence = IntelligenceEngine().build(db, site_id, analysis_id)
    history = build_history(db, site_id)
    content = ReportingAgent().generate(
        intelligence,
        history,
        report_type=report_type,
    )

    report = RiskReport(
        site_id=site_id,
        analysis_id=analysis_id,
        report_type=report_type,
        status="completed",
        title=content.get("title", "Risk Intelligence Report"),
        summary=content.get("summary", ""),
        content=content,
        generated_by=generated_by,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    logger.info(
        "report generated report_id=%s site=%s analysis=%s by=%s",
        report.id, site_id, analysis_id, generated_by or "system",
    )
    return report


def report_to_dict(db: Session, report: RiskReport) -> dict:
    analysis = (
        db.query(VideoAnalysis).filter(VideoAnalysis.id == report.analysis_id).first()
    )
    snapshot = None
    if analysis is not None:
        snapshot = {
            "timestamp": (
                analysis.timestamp.isoformat(timespec="seconds")
                if analysis.timestamp else None
            ),
            "video_source": analysis.original_filename or "",
            "source_type": analysis.source_type,
            "frames_analyzed": analysis.frames_analyzed,
            "model_used": analysis.model_used or "",
        }
    return {
        "id": report.id,
        "site_id": report.site_id,
        "analysis_id": report.analysis_id,
        "report_type": report.report_type,
        "status": report.status,
        "title": report.title,
        "summary": report.summary,
        "content": report.content or {},
        "generated_by": report.generated_by,
        "created_at": (
            report.created_at.isoformat(timespec="seconds") if report.created_at else None
        ),
        "analysis_snapshot": snapshot,
    }


def render_text(db: Session, report: RiskReport) -> str:
    """Plain-text rendering of a report (evidence-only, self-contained, 13 sections)."""
    content = report.content or {}
    exec_summary = content.get("executive_summary") or {}
    sections = content.get("sections") or {}
    site_info = content.get("site_info") or {}
    analysis_info = content.get("analysis_info") or {}
    limitations = content.get("limitations") or []
    hist = content.get("historical_analytics") or {}

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"{content.get('title', 'RISK INTELLIGENCE REPORT').upper()}")
    lines.append("=" * 72)
    lines.append(f"Report ID : {report.id}")
    lines.append(f"Site ID   : {report.site_id}")
    lines.append(f"Site Name : {site_info.get('site_name') or 'NOT_AVAILABLE'}")
    lines.append(f"Analysis  : {report.analysis_id}")
    if analysis_info.get("video_source"):
        lines.append(f"Video     : {analysis_info.get('video_source')}")
    if analysis_info.get("frames_analyzed") is not None:
        lines.append(f"Frames    : {analysis_info.get('frames_analyzed')} · Model: {analysis_info.get('model_used') or 'NOT_AVAILABLE'}")
    lines.append(f"Generated : {report.created_at}")
    lines.append("")

    lines.append("1. EXECUTIVE SUMMARY")
    lines.append("-" * 40)
    lines.append(exec_summary.get("short_line") or exec_summary.get("response") or "Not available.")
    for c in exec_summary.get("key_concerns") or []:
        lines.append(f"  • {c}")
    lines.append("")

    risk = sections.get("risk") or {}
    if risk.get("status") == "AVAILABLE":
        lines.append("2. OVERALL RISK")
        lines.append("-" * 40)
        lines.append(risk.get("summary") or "Not available.")
        lines.append(f"  Level: {risk.get('risk_level', 'NOT_AVAILABLE')} · Score: {risk.get('overall_score')}")
        for comp in risk.get("components") or []:
            sc = comp.get("score")
            sc_s = f"{sc:.0f}" if isinstance(sc, (int, float)) else "NOT_AVAILABLE"
            lines.append(f"  - {comp.get('label')}: {sc_s}")
        lines.append("")

    srisk = risk.get("site_risk") or {}
    if srisk and isinstance(srisk, dict):
        lines.append("3. SITE RISK")
        lines.append("-" * 40)
        lines.append(f"  Hazards: {srisk.get('hazards_total', 0)} · Open violations: {srisk.get('open_violation_count', 0)} · Alerts: {srisk.get('alert_count', 0)}")
        lines.append("")

    for key, label in (
        ("safety", "4. SAFETY"),
        ("compliance", "5. COMPLIANCE"),
        ("insurance", "6. INSURANCE"),
    ):
        section = sections.get(key) or {}
        lines.append(f"{label}")
        lines.append("-" * 40)
        lines.append(section.get("summary") or "Not available.")
        if key == "safety" and section.get("overall_safety_level"):
            lines.append(f"  Level: {section.get('overall_safety_level')} · Score: {section.get('overall_safety_score')}")
            if section.get("ppe_compliance_rate") is not None:
                lines.append(f"  PPE compliance: {section.get('ppe_compliance_rate') * 100:.0f}%")
        if key == "compliance" and section.get("compliance_level"):
            lines.append(f"  Level: {section.get('compliance_level')}")
        if key == "insurance" and section.get("claim_records") is not None:
            lines.append(f"  Claims on record: {section.get('claim_records')}")
        lines.append("")

    findings = (content.get("critical_findings") or []) + (content.get("high_findings") or [])
    lines.append("7. CRITICAL & HIGH FINDINGS")
    lines.append("-" * 40)
    if findings:
        for f in findings:
            sev = f.get("severity", "LOW")
            lines.append(f"  [{sev}] {f.get('title') or f.get('hazard_type') or 'Finding'} — {f.get('description', '')}")
    else:
        lines.append("  None recorded for this analysis.")
    lines.append("")

    prio = content.get("prioritized_actions") or []
    lines.append("8. RECOMMENDATIONS (PRIORITIZED ACTIONS)")
    lines.append("-" * 40)
    if prio:
        for a in prio:
            lines.append(f"  [{a.get('priority', 'MEDIUM')}] {a.get('title', '')}")
    else:
        lines.append("  No persisted recommendations for this analysis.")
    lines.append("")

    lines.append("9. HISTORICAL ANALYTICS")
    lines.append("-" * 40)
    lines.append(hist.get("message") or "Historical trend unavailable.")
    lines.append(f"  Analyses on record: {hist.get('analysis_count', 0)}")
    lines.append("")

    evidence = content.get("evidence_summary") or {}
    dq = evidence.get("data_quality") or content.get("data_quality") or {}
    lines.append("10. EVIDENCE & DATA QUALITY")
    lines.append("-" * 40)
    lines.append(f"  Quality: {dq.get('status', 'NOT_AVAILABLE')}")
    counts = evidence.get("counts") or {}
    if counts:
        lines.append("  Evidence counts: " + ", ".join(f"{k.replace('_', ' ')}={v}" for k, v in counts.items()))
    elif dq.get("note"):
        lines.append(f"  {dq.get('note')}")
    lines.append("")

    lines.append("11. LIMITATIONS")
    lines.append("-" * 40)
    for lim in limitations:
        lines.append(f"  • {lim}")
    lines.append("")

    lines.append("END OF REPORT")
    return "\n".join(lines)


__all__ = [
    "AnalysisNotFoundError",
    "IntelligenceError",
    "generate_report",
    "render_text",
    "report_to_dict",
]