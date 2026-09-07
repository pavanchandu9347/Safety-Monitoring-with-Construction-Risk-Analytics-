import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database.database import get_db
from app.models.models import RiskAssessment, Recommendation, Site
from app.schemas.schemas import RiskAssessmentResponse, RecommendationResponse, RiskTrendPoint
from app.services.analysis_pipeline import run_analysis, build_analysis_response, get_latest_analysis

router = APIRouter()


@router.get("/sites/{site_id}/risk", response_model=RiskAssessmentResponse)
def get_current_risk(site_id: str, db: Session = Depends(get_db)):
    risk = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.site_id == site_id)
        .order_by(RiskAssessment.timestamp.desc())
        .first()
    )
    if not risk:
        raise HTTPException(status_code=404, detail="No risk assessment yet — run a video analysis")
    return risk


@router.get("/sites/{site_id}/risk/history", response_model=list[RiskTrendPoint])
def get_risk_history(site_id: str, limit: int = 50, db: Session = Depends(get_db)):
    assessments = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.site_id == site_id)
        .order_by(RiskAssessment.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        RiskTrendPoint(timestamp=a.timestamp, score=a.overall_score, risk_level=a.risk_level)
        for a in reversed(assessments)
    ]


@router.get("/sites/{site_id}/recommendations", response_model=list[RecommendationResponse])
def get_recommendations(site_id: str, db: Session = Depends(get_db)):
    return (
        db.query(Recommendation)
        .filter(Recommendation.site_id == site_id)
        .order_by(Recommendation.created_at.desc())
        .all()
    )


@router.post("/sites/{site_id}/risk/analyze")
def run_risk_analysis(site_id: str, db: Session = Depends(get_db)) -> dict:
    """Re-run the unified video pipeline and return its risk payload.

    The pipeline is the platform's single analysis path: one input video, one
    ``analysis_id``, all agents consuming the same video-derived evidence.
    """
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    result = run_analysis(db, site_id=site_id)
    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))

    return {
        "status": "success",
        "analysis_id": result["analysis_id"],
        "risk_assessment": result.get("risk", {}),
        "hazards_count": len(result.get("hazards", [])),
        "recommendations_count": len(result.get("recommendations", [])),
        "worker_count": result.get("worker_count", 0),
        "video": result.get("video", {}),
        "evidence_note": result.get("evidence_note", ""),
    }


@router.get("/sites/{site_id}/risk/latest")
def get_latest_risk_analysis(site_id: str, db: Session = Depends(get_db)):
    """Full latest-analysis payload (risk + safety + evidence)."""
    analysis = get_latest_analysis(db, site_id)
    if not analysis:
        return {"status": "none", "message": "No video analysis yet. Run Analyze Video first."}
    return build_analysis_response(db, analysis)