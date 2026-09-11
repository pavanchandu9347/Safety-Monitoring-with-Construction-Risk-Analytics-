import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.models import (
    Site, ComplianceRequirement, ComplianceFinding, InspectionRecord, ComplianceAssessment,
)
from app.schemas.schemas import (
    ComplianceRequirementResponse, ComplianceFindingResponse, InspectionRecordResponse,
    ComplianceAssessmentResponse, ComplianceDashboardResponse,
)
from app.services.analysis_pipeline import run_analysis, get_latest_analysis
from app.services.compliance_baseline import ensure_compliance_baseline

router = APIRouter()


def _get_site_or_404(db: Session, site_id: str) -> Site:
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


def _policy_violation_summary(db: Session, site_id: str) -> list[dict]:
    from app.models.models import SafetyViolation
    rows = (
        db.query(SafetyViolation)
        .filter(SafetyViolation.site_id == site_id, SafetyViolation.status == "open")
        .order_by(SafetyViolation.timestamp.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "violation_type": v.violation_type,
            "description": v.description,
            "severity": v.severity,
            "source": v.source,
            "timestamp": v.timestamp.isoformat() if v.timestamp else None,
        }
        for v in rows
    ]


@router.post("/sites/{site_id}/compliance/analyze")
def run_compliance_analysis(site_id: str, db: Session = Depends(get_db)) -> dict:
    """Run (or reuse) the unified video analysis and return its compliance payload.

    Compliance results come from the shared pipeline so they share the same
    ``analysis_id`` and video evidence as safety, risk and insurance results.
    """
    _get_site_or_404(db, site_id)

    result = run_analysis(db, site_id=site_id)
    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))

    compliance = result.get("compliance", {})
    return {
        "status": "success",
        "analysis_id": result["analysis_id"],
        "compliance_assessment": compliance.get("compliance_level"),
        "overall_score": compliance.get("overall_score"),
        "compliance": compliance,
        "requirements_checked": compliance.get("requirements_checked", 0),
        "compliant_count": compliance.get("compliant_count", 0),
        "non_compliant_count": compliance.get("non_compliant_count", 0),
        "not_verified_count": compliance.get("not_verified_count", 0),
        "open_violations": compliance.get("open_violations", 0),
        "recommendations_count": len(compliance.get("recommendations", [])),
        "evidence_note": result.get("evidence_note", ""),
    }


@router.get("/sites/{site_id}/compliance/dashboard", response_model=ComplianceDashboardResponse)
def get_compliance_dashboard(site_id: str, db: Session = Depends(get_db)):
    site = _get_site_or_404(db, site_id)
    ensure_compliance_baseline(db, site_id)

    assessment = (
        db.query(ComplianceAssessment)
        .filter(ComplianceAssessment.site_id == site_id)
        .order_by(ComplianceAssessment.timestamp.desc())
        .first()
    )
    latest = get_latest_analysis(db, site_id)

    requirements = (
        db.query(ComplianceRequirement)
        .filter(ComplianceRequirement.site_id == site_id)
        .order_by(ComplianceRequirement.category)
        .all()
    )
    findings = (
        db.query(ComplianceFinding)
        .filter(
            ComplianceFinding.site_id == site_id,
            ComplianceFinding.analysis_id == (latest.id if latest else ComplianceFinding.analysis_id),
        ) if latest else db.query(ComplianceFinding).filter(ComplianceFinding.site_id == site_id)
    ).order_by(ComplianceFinding.timestamp.desc()).limit(100).all()

    inspections = (
        db.query(InspectionRecord)
        .filter(InspectionRecord.site_id == site_id)
        .order_by(InspectionRecord.status.desc())
        .limit(50)
        .all()
    )

    report = assessment.report if assessment and isinstance(assessment.report, dict) else {}
    recommendations = assessment.recommendations if assessment else []
    recommendations = recommendations if isinstance(recommendations, list) else []
    unavailable = report.get("unavailable_evidence", []) if isinstance(report, dict) else []

    compliant = sum(1 for f in findings if f.status == "COMPLIANT")
    non_compliant = sum(1 for f in findings if f.status == "NON_COMPLIANT")
    not_verified = sum(1 for f in findings if f.status == "NOT_VERIFIED")
    overdue_inspections = sum(1 for i in inspections if i.status == "OVERDUE")

    return ComplianceDashboardResponse(
        site_id=site_id,
        site_name=site.name,
        generated_at=datetime.now(timezone.utc),
        current_assessment=assessment,
        requirements=[ComplianceRequirementResponse.model_validate(r) for r in requirements],
        findings=[ComplianceFindingResponse.model_validate(f) for f in findings],
        inspections=[InspectionRecordResponse.model_validate(i) for i in inspections],
        policy_violations=_policy_violation_summary(db, site_id),
        recommendations=recommendations,
        unavailable_evidence=unavailable,
        total_requirements=len(requirements),
        compliant=compliant,
        non_compliant=non_compliant,
        not_verified=not_verified,
        overdue_inspections=overdue_inspections,
    )


@router.get("/sites/{site_id}/compliance/findings", response_model=list[ComplianceFindingResponse])
def list_compliance_findings(site_id: str, db: Session = Depends(get_db)):
    return (
        db.query(ComplianceFinding)
        .filter(ComplianceFinding.site_id == site_id)
        .order_by(ComplianceFinding.timestamp.desc())
        .limit(100)
        .all()
    )


@router.get("/sites/{site_id}/compliance/requirements", response_model=list[ComplianceRequirementResponse])
def list_compliance_requirements(site_id: str, db: Session = Depends(get_db)):
    _get_site_or_404(db, site_id)
    ensure_compliance_baseline(db, site_id)
    return (
        db.query(ComplianceRequirement)
        .filter(ComplianceRequirement.site_id == site_id)
        .order_by(ComplianceRequirement.category)
        .all()
    )


@router.get("/sites/{site_id}/compliance/inspections", response_model=list[InspectionRecordResponse])
def list_inspections(site_id: str, db: Session = Depends(get_db)):
    _get_site_or_404(db, site_id)
    ensure_compliance_baseline(db, site_id)
    return (
        db.query(InspectionRecord)
        .filter(InspectionRecord.site_id == site_id)
        .order_by(InspectionRecord.status.desc())
        .limit(50)
        .all()
    )


@router.get("/sites/{site_id}/compliance/assessment", response_model=ComplianceAssessmentResponse)
def get_compliance_assessment(site_id: str, db: Session = Depends(get_db)):
    _get_site_or_404(db, site_id)
    assessment = (
        db.query(ComplianceAssessment)
        .filter(ComplianceAssessment.site_id == site_id)
        .order_by(ComplianceAssessment.timestamp.desc())
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="No compliance assessment available")
    return assessment