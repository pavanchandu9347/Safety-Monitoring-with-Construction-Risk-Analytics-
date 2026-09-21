"""Historical Analytics for the Construction Risk Intelligence Engine (M4).

Builds a per-site analytics series from the REAL persisted per-analysis rows
only. Trend points map 1:1 to completed ``VideoAnalysis`` passes; no synthetic
points are ever inserted. With fewer than two analyses the trend is explicitly
marked unavailable ("INSUFFICIENT_DATA") rather than extrapolated.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.models import (
    ComplianceAssessment,
    Hazard,
    InsuranceAssessment,
    RiskAssessment,
    SafetyAlert,
    SafetyAssessment,
    SafetyViolation,
    Site,
    VideoAnalysis,
)

_S = "INSUFFICIENT_DATA"
_MESSAGE = (
    "Historical trend unavailable — only one analysis is available. "
    "Run the site video analysis at least twice to build a trend."
)


def _iso(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat(timespec="seconds")
    return str(value)


def _level(value: Optional[Any]) -> str:
    level = str(value or "").upper()
    if level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        return level
    return "NOT_AVAILABLE"


def _num(value: Optional[Any]) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _sev_counts(db: Session, site_id: str, analysis_id: str, model, severity_col) -> dict:
    rows = (
        db.query(model).filter(model.site_id == site_id, model.analysis_id == analysis_id).all()
    )
    out = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for row in rows:
        level = str(getattr(row, severity_col) or "LOW").upper()
        out[level] = out.get(level, 0) + 1
    return out


def build_history(db: Session, site_id: str) -> dict:
    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        return {
            "site_id": site_id,
            "status": "SITE_NOT_FOUND",
            "count": 0,
            "trend_available": False,
            "message": f"Site {site_id} does not exist.",
            "series": [],
        }

    analyses = (
        db.query(VideoAnalysis)
        .filter(VideoAnalysis.site_id == site_id)
        .order_by(VideoAnalysis.timestamp.asc())
        .all()
    )

    series = []
    for analysis in analyses:
        risk = (
            db.query(RiskAssessment)
            .filter(RiskAssessment.analysis_id == analysis.id)
            .order_by(RiskAssessment.timestamp.desc())
            .first()
        )
        safety = (
            db.query(SafetyAssessment)
            .filter(SafetyAssessment.analysis_id == analysis.id)
            .order_by(SafetyAssessment.timestamp.desc())
            .first()
        )
        compliance = (
            db.query(ComplianceAssessment)
            .filter(ComplianceAssessment.analysis_id == analysis.id)
            .order_by(ComplianceAssessment.timestamp.desc())
            .first()
        )
        insurance = (
            db.query(InsuranceAssessment)
            .filter(InsuranceAssessment.analysis_id == analysis.id)
            .order_by(InsuranceAssessment.timestamp.desc())
            .first()
        )

        series.append(
            {
                "analysis_id": analysis.id,
                "timestamp": _iso(analysis.timestamp),
                "video_source": analysis.original_filename or "",
                "status": analysis.status,
                "risk_score": _num(risk.overall_score) if risk else None,
                "risk_level": _level(risk.risk_level) if risk else "NOT_AVAILABLE",
                "safety_score": _num(safety.overall_safety_score) if safety else None,
                "safety_level": _level(safety.overall_safety_level) if safety else "NOT_AVAILABLE",
                "ppe_compliance_rate": _num(safety.ppe_compliance_rate) if safety else None,
                "compliance_score": _num(compliance.overall_score) if compliance else None,
                "compliance_level": _level(compliance.compliance_level) if compliance else "NOT_AVAILABLE",
                "insurance_score": _num(insurance.risk_score) if insurance else None,
                "insurance_level": _level(insurance.risk_level) if insurance else "NOT_AVAILABLE",
                "hazard_count": sum(
                    _sev_counts(db, site_id, analysis.id, Hazard, "severity").values()
                ),
                "violation_count": sum(
                    _sev_counts(db, site_id, analysis.id, SafetyViolation, "severity").values()
                ),
                "alert_count": sum(
                    _sev_counts(db, site_id, analysis.id, SafetyAlert, "severity").values()
                ),
                "worker_count": _num(
                    safety.worker_count if safety else None
                ),
                "critical_findings": (
                    _sev_counts(db, site_id, analysis.id, Hazard, "severity").get("CRITICAL", 0)
                    + _sev_counts(db, site_id, analysis.id, SafetyViolation, "severity").get("CRITICAL", 0)
                    + _sev_counts(db, site_id, analysis.id, SafetyAlert, "severity").get("CRITICAL", 0)
                ),
            }
        )

    count = len(series)
    trend_available = count >= 2

    return {
        "site_id": site_id,
        "site_name": site.name,
        "count": count,
        "status": _S if not trend_available else "AVAILABLE",
        "trend_available": trend_available,
        "message": "" if trend_available else _MESSAGE,
        "series": series,
    }