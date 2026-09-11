"""Unified video-analysis API — the platform's single primary input.

    POST /api/video/analyze      multipart(file? | video_path?, site_id?, conf?)
    GET  /api/video/source       list of construction-site videos in the project
    GET  /api/video/analysis/{analysis_id}            full per-analysis payload
    GET  /api/sites/{site_id}/video/analysis          analysis history
    GET  /api/sites/{site_id}/video/analysis/latest   most recent analysis

Every analysis builds one ``analysis_id`` shared by all result rows.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.config import default_video_source, discover_videos
from app.database.database import get_db
from app.models.models import VideoAnalysis, Site, Manager
from app.auth.deps import require_auth, authorize_site
from app.services.analysis_pipeline import (
    build_analysis_response,
    get_latest_analysis,
    run_analysis,
)

router = APIRouter()


@router.get("/video/source")
def list_video_sources(site_id: str = "site_riverside_main"):
    """List candidate construction-site videos (project folder + uploads)."""
    videos = discover_videos()
    default = default_video_source()
    storage = None
    found_default = None
    for v in videos:
        if v["path"] == default:
            found_default = v
        if "data/videos" in v["path"] and storage is None:
            storage = v
    return {
        "site_id": site_id,
        "default": found_default or (videos[0] if len(videos) == 1 else None),
        "videos": videos,
        "hint": (
            "Single input video: " + (videos[0]["name"] if len(videos) == 1 else "select a video")
        ),
    }


@router.post("/video/analyze")
def analyze_video(
    site_id: str = Form("site_riverside_main"),
    video_path: str = Form(""),
    conf: float = Form(0.0),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    manager: Manager = Depends(require_auth),
):
    """Analyze exactly one video. Pass either an uploaded ``file`` or a
    ``video_path`` (from GET /video/source). Produces a new ``analysis_id``."""
    authorize_site(manager, site_id)
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    file_bytes = None
    filename = ""
    if file is not None and file.filename:
        file_bytes = file.file.read()
        filename = file.filename

    confidence = conf if conf and conf > 0 else None
    result = run_analysis(
        db,
        site_id=site_id,
        video_path=video_path,
        file_bytes=file_bytes,
        filename=filename,
        conf=confidence,
    )
    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
    return result


@router.get("/video/analysis/{analysis_id}")
def get_analysis(analysis_id: str, db: Session = Depends(get_db), manager: Manager = Depends(require_auth)):
    analysis = db.query(VideoAnalysis).filter(VideoAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    authorize_site(manager, analysis.site_id)
    return build_analysis_response(db, analysis)


@router.get("/sites/{site_id}/video/analysis")
def list_analyses(site_id: str, limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(VideoAnalysis)
        .filter(VideoAnalysis.site_id == site_id)
        .order_by(VideoAnalysis.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "analysis_id": a.id,
            "status": a.status,
            "filename": a.original_filename,
            "source_type": a.source_type,
            "worker_count": a.worker_count,
            "vehicle_count": a.vehicle_count,
            "ppe_compliance": a.ppe_compliance,
            "total_violations": a.total_violations,
            "frames_analyzed": a.frames_analyzed,
            "error": a.error,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        }
        for a in rows
    ]


@router.get("/sites/{site_id}/video/analysis/latest")
def latest_analysis(site_id: str, db: Session = Depends(get_db)):
    analysis = get_latest_analysis(db, site_id)
    if not analysis:
        return {
            "status": "none",
            "analysis_id": None,
            "message": "No video analysis yet. Run 'Analyze Video' to create one.",
        }
    return build_analysis_response(db, analysis)