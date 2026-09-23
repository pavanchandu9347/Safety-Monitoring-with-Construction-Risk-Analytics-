"""Reporting Intelligence API (Milestone 4 - Reporting Intelligence).

All routes are authenticated and site-authorized server-side (registered in
``app.main`` behind ``require_site_access``). The unified intelligence context,
historical analytics and reports all reference REAL persisted analysis rows —
missing evidence is surfaced as ``NOT_AVAILABLE`` / ``INSUFFICIENT_DATA``.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.auth.deps import get_current_manager
from app.database.database import get_db
from app.models.models import Manager, RiskReport, Site, VideoAnalysis
from app.services.analysis_pipeline import get_latest_analysis
from app.services.historical_analytics import build_history
from app.services.intelligence import (
    AnalysisNotFoundError,
    IntelligenceEngine,
    SiteNotFoundError,
    maybe_notify,
)
from app.services.report_service import (
    generate_report,
    render_pdf,
    render_text,
    report_to_dict,
)

router = APIRouter()

logger = logging.getLogger(__name__)


def _get_site_or_404(db: Session, site_id: str) -> Site:
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


def _resolve_analysis(
    db: Session, site_id: str, analysis_id: Optional[str]
) -> VideoAnalysis:
    if analysis_id:
        analysis = (
            db.query(VideoAnalysis)
            .filter(
                VideoAnalysis.id == analysis_id,
                VideoAnalysis.site_id == site_id,
            )
            .first()
        )
        if analysis is None:
            raise HTTPException(
                status_code=404,
                detail=f"Analysis {analysis_id} not found for site {site_id}",
            )
        return analysis
    analysis = get_latest_analysis(db, site_id)
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis available yet — run the site risk analysis first",
        )
    return analysis


class ReportGenerateRequest(BaseModel):
    analysis_id: Optional[str] = Field(default=None, description="Target analysis. Defaults to the latest analysis for the site.")
    report_type: str = Field(default="risk_intelligence")


@router.post("/sites/{site_id}/reports/generate")
def create_report(
    site_id: str,
    body: ReportGenerateRequest,
    db: Session = Depends(get_db),
    manager: Manager = Depends(get_current_manager),
) -> dict:
    """Generate and persist an executive risk report for one real analysis."""
    _get_site_or_404(db, site_id)
    analysis = _resolve_analysis(db, site_id, body.analysis_id)

    try:
        report = generate_report(
            db,
            site_id,
            analysis.id,
            generated_by=manager.id,
            report_type=body.report_type,
        )
    except (SiteNotFoundError, AnalysisNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Raise qualified notifications from persisted results. Deliberately
    # failure-safe: a notification backend error is logged and skipped so it
    # can NEVER turn a successfully persisted report into a failed request.
    created = 0
    try:
        created = maybe_notify(db, site_id, analysis.id)
    except Exception as exc:  # pragma: no cover - defensive, notification-safe
        logger.warning(
            "notification pass skipped after report generation "
            "report_id=%s site=%s error=%s",
            report.id, site_id, exc,
        )

    payload = report_to_dict(db, report)
    payload["notifications_raised"] = created
    return payload


@router.get("/sites/{site_id}/reports")
def list_reports(
    site_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict:
    _get_site_or_404(db, site_id)
    reports = (
        db.query(RiskReport)
        .options(selectinload(RiskReport.analysis))
        .filter(RiskReport.site_id == site_id)
        .order_by(RiskReport.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return {
        "site_id": site_id,
        "count": len(reports),
        "reports": [report_to_dict(db, r) for r in reports],
    }


@router.get("/sites/{site_id}/reports/latest")
def get_latest_report(
    site_id: str,
    db: Session = Depends(get_db),
) -> dict:
    _get_site_or_404(db, site_id)
    report = (
        db.query(RiskReport)
        .options(selectinload(RiskReport.analysis))
        .filter(RiskReport.site_id == site_id)
        .order_by(RiskReport.created_at.desc())
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="No report generated yet")
    return report_to_dict(db, report)


@router.get("/sites/{site_id}/reports/{report_id}")
def get_report(
    site_id: str,
    report_id: str,
    db: Session = Depends(get_db),
) -> dict:
    _get_site_or_404(db, site_id)
    report = (
        db.query(RiskReport)
        .options(selectinload(RiskReport.analysis))
        .filter(RiskReport.id == report_id, RiskReport.site_id == site_id)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report_to_dict(db, report)


@router.get("/sites/{site_id}/reports/{report_id}/text")
def get_report_text(
    site_id: str,
    report_id: str,
    db: Session = Depends(get_db),
) -> dict:
    _get_site_or_404(db, site_id)
    report = (
        db.query(RiskReport)
        .filter(RiskReport.id == report_id, RiskReport.site_id == site_id)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"report_id": report.id, "text": render_text(db, report)}


@router.get("/sites/{site_id}/reports/{report_id}/pdf")
def get_report_pdf(
    site_id: str,
    report_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Export one report as a downloadable A4 PDF (evidence-only content)."""
    _get_site_or_404(db, site_id)
    report = (
        db.query(RiskReport)
        .filter(RiskReport.id == report_id, RiskReport.site_id == site_id)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    pdf_bytes = render_pdf(db, report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="buildsure-report-{report.id[:12]}.pdf"'
            )
        },
    )


@router.get("/sites/{site_id}/intelligence")
def get_intelligence(
    site_id: str,
    analysis_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """Unified intelligence context for an analysis (or the latest one)."""
    _get_site_or_404(db, site_id)
    analysis = _resolve_analysis(db, site_id, analysis_id)
    try:
        return IntelligenceEngine().build(db, site_id, analysis.id)
    except (SiteNotFoundError, AnalysisNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/sites/{site_id}/analytics/history")
def get_history(
    site_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Per-site historical analytics built from real analysis rows only."""
    _get_site_or_404(db, site_id)
    return build_history(db, site_id)