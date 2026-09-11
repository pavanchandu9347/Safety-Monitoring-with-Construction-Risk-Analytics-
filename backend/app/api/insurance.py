import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.models import (
    Site, InsuranceAssessment, InsuranceIncident, ClaimRecord,
)
from app.schemas.schemas import (
    InsuranceAssessmentResponse, InsuranceIncidentResponse, ClaimRecordResponse,
    InsuranceDashboardResponse,
)
from app.services.analysis_pipeline import run_analysis

router = APIRouter()


def _get_site_or_404(db: Session, site_id: str) -> Site:
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.post("/sites/{site_id}/insurance/analyze")
def run_insurance_analysis(site_id: str, db: Session = Depends(get_db)) -> dict:
    """Run (or reuse) the unified video analysis and return its insurance payload.

    Insurance results come from the shared pipeline so they share the same
    ``analysis_id`` and video evidence as safety, risk and insurance results.
    """
    _get_site_or_404(db, site_id)

    result = run_analysis(db, site_id=site_id)
    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))

    insurance = result.get("insurance", {})
    return {
        "status": "success",
        "analysis_id": result["analysis_id"],
        "insurance_assessment": insurance,
        "insurance_risk_score": insurance.get("insurance_risk_score", 0),
        "risk_level": insurance.get("risk_level", "LOW"),
        "incident_count": insurance.get("incident_count", 0),
        "recommendations_count": len(insurance.get("recommendations", [])),
        "evidence_note": result.get("evidence_note", ""),
    }


@router.get("/sites/{site_id}/insurance/dashboard", response_model=InsuranceDashboardResponse)
def get_insurance_dashboard(site_id: str, db: Session = Depends(get_db)):
    site = _get_site_or_404(db, site_id)

    assessment = (
        db.query(InsuranceAssessment)
        .filter(InsuranceAssessment.site_id == site_id)
        .order_by(InsuranceAssessment.timestamp.desc())
        .first()
    )
    incidents = (
        db.query(InsuranceIncident)
        .filter(InsuranceIncident.site_id == site_id)
        .order_by(InsuranceIncident.timestamp.desc())
        .limit(50)
        .all()
    )
    claim_records = (
        db.query(ClaimRecord)
        .filter(ClaimRecord.site_id == site_id)
        .order_by(ClaimRecord.created_at.desc())
        .limit(50)
        .all()
    )

    claim_documentation = {"status": "NO_CLAIM_DOCUMENTATION", "count": 0, "documents": []}
    if claim_records:
        docs = [c.documentation[0] for c in claim_records if isinstance(c.documentation, list) and c.documentation]
        claim_documentation = {
            "status": "AVAILABLE",
            "count": len(claim_records),
            "documents": docs,
        }

    recommendations = []
    if assessment and isinstance(assessment.recommendations, list):
        recommendations = assessment.recommendations

    open_incidents = sum(1 for i in incidents if i.severity in ("HIGH", "CRITICAL"))
    open_claims = sum(1 for c in claim_records if c.status == "DRAFTED")

    return InsuranceDashboardResponse(
        site_id=site_id,
        site_name=site.name,
        generated_at=datetime.now(timezone.utc),
        current_assessment=assessment,
        incidents=[InsuranceIncidentResponse.model_validate(i) for i in incidents],
        claim_records=[ClaimRecordResponse.model_validate(c) for c in claim_records],
        claim_documentation=claim_documentation,
        recommendations=recommendations,
        incident_count=len(incidents),
        open_incidents=open_incidents,
        open_claims=open_claims,
    )


@router.get("/sites/{site_id}/insurance/incidents", response_model=list[InsuranceIncidentResponse])
def list_incidents(site_id: str, db: Session = Depends(get_db)):
    return (
        db.query(InsuranceIncident)
        .filter(InsuranceIncident.site_id == site_id)
        .order_by(InsuranceIncident.timestamp.desc())
        .limit(100)
        .all()
    )


@router.get("/sites/{site_id}/insurance/claims", response_model=list[ClaimRecordResponse])
def list_claims(site_id: str, db: Session = Depends(get_db)):
    return (
        db.query(ClaimRecord)
        .filter(ClaimRecord.site_id == site_id)
        .order_by(ClaimRecord.created_at.desc())
        .limit(100)
        .all()
    )


@router.get("/sites/{site_id}/insurance/assessment", response_model=InsuranceAssessmentResponse)
def get_insurance_assessment(site_id: str, db: Session = Depends(get_db)):
    _get_site_or_404(db, site_id)
    assessment = (
        db.query(InsuranceAssessment)
        .filter(InsuranceAssessment.site_id == site_id)
        .order_by(InsuranceAssessment.timestamp.desc())
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="No insurance assessment available")
    return assessment