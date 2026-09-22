"""Unified video-analysis API — the platform's single primary input.

    POST /api/video/analyze      multipart(file? | video_path?, site_id?, conf?)
    GET  /api/video/source       list of construction-site videos in the project
    GET  /api/video/analysis/{analysis_id}            full per-analysis payload
    GET  /api/sites/{site_id}/video/analysis          analysis history
    GET  /api/sites/{site_id}/video/analysis/latest   most recent analysis

Every analysis builds one ``analysis_id`` shared by all result rows. Uploads are
streamed to disk (bounded by ``MAX_UPLOAD_SIZE_MB``) and the CPU-heavy pipeline
runs in the background: the POST returns immediately with ``status: "queued"``.
"""

from __future__ import annotations

import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.config import (
    MAX_UPLOAD_SIZE_BYTES,
    MAX_UPLOAD_SIZE_MB,
    REPO_ROOT,
    VIDEO_EXTENSIONS,
    default_video_source,
    discover_videos,
    ensure_storage,
)
from app.database.database import get_db
from app.models.models import VideoAnalysis, Site, Manager
from app.auth.deps import require_auth, authorize_site
from app.services.analysis_pipeline import (
    _sanitize_filename,
    build_analysis_response,
    get_latest_analysis,
    process_analysis_background,
    queue_analysis,
)

router = APIRouter()


def _save_upload_streamed(file: UploadFile) -> str:
    """Stream an uploaded video to storage with an enforced size limit.

    Rejects unsupported extensions (400) and files larger than
    ``MAX_UPLOAD_SIZE_MB`` (413). The file is copied in 1 MB chunks and never
    loaded entirely into RAM; a partial copy is always cleaned up on failure.
    """
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported video type '{ext or 'unknown'}'. "
                f"Allowed: {', '.join(VIDEO_EXTENSIONS)}"
            ),
        )
    if file.size is not None and file.size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Upload of {file.size / (1024 * 1024):.1f} MB exceeds the "
                f"{MAX_UPLOAD_SIZE_MB} MB limit."
            ),
        )

    folder = ensure_storage()
    dest = folder / f"{datetime.now():%Y%m%d_%H%M%S}_{_sanitize_filename(filename)}"
    written = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds the {MAX_UPLOAD_SIZE_MB} MB limit.",
                    )
                out.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    if written == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    return str(dest)


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
    background_tasks: BackgroundTasks,
    site_id: str = Form("site_riverside_main"),
    video_path: str = Form(""),
    conf: float = Form(0.0),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    manager: Manager = Depends(require_auth),
):
    """Analyze exactly one video. Pass either an uploaded ``file`` or a
    ``video_path`` (from GET /video/source).

    The request is acknowledged immediately with ``status: "queued"`` and an
    ``analysis_id``; the heavy YOLO/agent pipeline runs in the background.
    Poll GET /video/analysis/{analysis_id} for the final result.
    """
    authorize_site(manager, site_id)
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    resolved_path = ""
    filename = ""
    source_type = "stored"
    if file is not None and file.filename:
        resolved_path = _save_upload_streamed(file)
        filename = Path(resolved_path).name
        source_type = "uploaded"
    else:
        if video_path:
            p = Path(video_path)
            if not p.is_absolute():
                p = REPO_ROOT / p
            if not p.is_file():
                raise HTTPException(status_code=400, detail=f"Video not found: {video_path}")
            resolved_path = str(p)
            filename = p.name
        else:
            default = default_video_source()
            if not (default and Path(default).is_file()):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No video available. Upload a construction-site video or "
                        "select a stored source from GET /api/video/source."
                    ),
                )
            resolved_path = default
            filename = Path(default).name

    analysis = queue_analysis(
        db,
        site_id=site_id,
        filename=filename,
        stored_path=resolved_path,
        source_type=source_type,
    )
    confidence = conf if conf and conf > 0 else None
    background_tasks.add_task(
        process_analysis_background,
        analysis.id,
        site_id,
        resolved_path,
        confidence,
    )
    return {
        "status": analysis.status,
        "analysis_id": analysis.id,
        "site_id": site_id,
        "video": {
            "filename": filename,
            "path": resolved_path,
            "source_type": source_type,
        },
        "message": (
            "Analysis queued. Poll GET /api/video/analysis/{analysis_id} for status."
        ),
    }


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