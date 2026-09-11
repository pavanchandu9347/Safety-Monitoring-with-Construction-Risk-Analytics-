"""Unified video-analysis pipeline (single primary input).

The platform's ONE construction-site video is the single source of truth:

    video ──► frames ──► YOLO(base) + PPE ──► evidence ──► agents ──► records

* Uploads store the video under ``VIDEO_STORAGE_PATH``; stored videos are
  discovered from the project folder when no explicit path is given.
* One ``analysis_id`` (a ``VideoAnalysis`` row) is created and every downstream
  record (monitoring events, hazards, risk assessments, recommendations,
  observed equipment, workers, safety violations, alerts, safety assessments)
  carries that ``analysis_id``.
* Only REAL evidence from the video is used. No random, hardcoded or simulated
  analysis results are produced. Where the video cannot support a dimension
  (weather, ground condition, …) the agents score ``0`` and an evidence note is
  attached instead of inventing data.
"""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import REPO_ROOT, ensure_storage
from app.models.models import (
    ClaimRecord,
    ComplianceAssessment,
    ComplianceFinding,
    ComplianceRequirement,
    Equipment,
    Hazard,
    InspectionRecord,
    InsuranceAssessment,
    InsuranceIncident,
    MonitoringEvent,
    Recommendation,
    RiskAssessment,
    RiskAssessmentHazard,
    SafetyAlert,
    SafetyAssessment,
    SafetyViolation,
    Site,
    VideoAnalysis,
    Worker,
    Zone,
)
from app.services.safety_alerts import build_safety_alerts
from app.services.video_analysis import get_video_report
from app.services.notification_service import evaluate_analysis

_DEBUG = os.environ.get("TESTING") == "1"

# COCO classes mapped to construction-site equipment (only what the video shows).
_EQUIPMENT_BY_CLASS: Dict[int, tuple[str, str]] = {
    2: ("service_vehicle", "shuttling"),
    5: ("site_bus", "transport"),
    7: ("dump_truck", "hauling"),
    8: ("work_boat", "transport"),
}

_SEVERITY_MAP = {
    "low": "LOW",
    "medium": "MEDIUM",
    "high": "HIGH",
    "critical": "CRITICAL",
}


def _sanitize_filename(filename: str) -> str:
    name = Path(filename or "upload.mp4").name
    name = re.sub(r"[^\w.\-]", "_", name)
    return name or "upload.mp4"


def save_uploaded_video(file_bytes: bytes, filename: str) -> str:
    """Persist an uploaded video under the storage folder and return its path."""
    folder = ensure_storage()
    dest = folder / f"{datetime.now():%Y%m%d_%H%M%S}_{_sanitize_filename(filename)}"
    dest.write_bytes(file_bytes)
    return str(dest)


def _resolve_video(
    site_id: str,
    video_path: str = "",
    file_bytes: Optional[bytes] = None,
    filename: str = "",
) -> tuple[Optional[str], str]:
    """Resolve the analysis input.

    Priority: uploaded bytes, explicit video path, project default video,
    (test-only tiny synthetic clip under TESTING=1).

    Returns ``(path, source_type)`` where source_type is ``uploaded`` or
    ``stored``, or ``(None, reason)`` describing the failure.
    """
    if file_bytes is not None:
        if not file_bytes:
            return None, "Empty upload"
        return save_uploaded_video(file_bytes, filename), "uploaded"

    if video_path:
        p = Path(video_path)
        if not p.is_absolute():
            p = REPO_ROOT / p
        if not p.exists():
            return None, f"Video not found: {video_path}"
        if not p.is_file():
            return None, f"Not a video file: {video_path}"
        return str(p), "stored"

    from app.config import default_video_source

    default = default_video_source()
    if default and Path(default).is_file():
        return default, "stored"

    if _DEBUG:
        clip = _testing_clip()
        if clip:
            return clip, "stored"

    return None, "No video available. Upload a construction-site video or select a stored one."


_TESTING_CLIP_PATH: Optional[str] = None


def _testing_clip() -> Optional[str]:
    """Small real (but blank) clip used only when running the test-suite."""
    global _TESTING_CLIP_PATH
    if _TESTING_CLIP_PATH and Path(_TESTING_CLIP_PATH).exists():
        return _TESTING_CLIP_PATH

    try:
        import cv2
        import numpy as np

        path = os.path.join(tempfile.gettempdir(), "acrip_test_video.mp4")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (480, 270))
        if not writer.isOpened():
            return None
        for _ in range(20):
            writer.write(np.full((270, 480, 3), 90, dtype=np.uint8))
        writer.release()
        _TESTING_CLIP_PATH = path
        return path
    except Exception:
        return None


def _video_equipment(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build the equipment list strictly from objects the video actually shows.

    Evidence is gathered from every sampled frame (``frame_evidence``), taking
    the maximum simultaneous count per equipment class so the list reflects the
    vehicle fleet visible in the footage — not only the single best frame.
    """
    def per_class_from(frames, key: str):
        counts: Dict[int, int] = {}
        for frame in frames:
            per: Dict[int, int] = {}
            for d in frame.get(key, []):
                cid = d.get("class_id")
                if cid in _EQUIPMENT_BY_CLASS:
                    per[cid] = per.get(cid, 0) + 1
            for cid, n in per.items():
                if n > counts.get(cid, 0):
                    counts[cid] = n
        return counts

    counts = per_class_from(report.get("frame_evidence", []), "detections")
    for d in report.get("detected_objects", []):
        cid = d.get("class_id")
        if cid in _EQUIPMENT_BY_CLASS:
            counts[cid] = max(counts.get(cid, 0), 1)

    equipment: List[Dict[str, Any]] = []
    for cid, (etype, activity) in _EQUIPMENT_BY_CLASS.items():
        for i in range(1, counts.get(cid, 0) + 1):
            equipment.append({
                "name": f"{etype.replace('_', ' ').title()}-{i:02d}",
                "equipment_type": etype,
                "status": "active",
                "activity": activity,
                "zone_id": None,
                "nearby_worker_count": 0,
                "maintenance_status": "operational",
                "operating_duration_minutes": 0,
            })
    return equipment


def run_analysis(
    db: Session,
    site_id: str = "site_riverside_main",
    video_path: str = "",
    file_bytes: Optional[bytes] = None,
    filename: str = "",
    conf: Optional[float] = None,
) -> Dict[str, Any]:
    """Run the full video pipeline for one input video and persist the results."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        return {"status": "failed", "error": f"Site not found: {site_id}"}

    path, source_type = _resolve_video(site_id, video_path, file_bytes, filename)
    if not path:
        return {"status": "failed", "error": source_type}

    analysis = VideoAnalysis(
        site_id=site_id,
        original_filename=Path(path).name,
        stored_path=path,
        source_type=source_type,
        status="processing",
        frame_interval=int(os.environ.get("FRAME_SAMPLE_RATE", 15)),
        max_frames=int(os.environ.get("MAX_FRAMES", 30)),
    )
    db.add(analysis)
    db.flush()
    analysis_id = analysis.id

    try:
        import cv2
        from ai.computer_vision.frame_extractor import FrameExtractor

        meta = FrameExtractor().get_video_metadata(path)
        capture = cv2.VideoCapture(path)
        opened = bool(capture is not None and capture.isOpened())
        if capture is not None:
            capture.release()
        if not opened:
            raise RuntimeError(f"Cannot open video source: {path}")

        report = get_video_report(site_id=site_id, video_path=path, conf=conf, force=True)
        if report.get("error"):
            raise RuntimeError(report["error"])

        now = datetime.now(timezone.utc)

        detected_objects = report.get("detected_objects", [])
        worker_count = report.get("worker_count", 0)
        lighting = report.get("lighting_condition", "") or ""

        evidence_note = (
            "The video source has no environmental sensors; weather, temperature, "
            "wind and ground conditions are not available from current video "
            "evidence."
        )
        site_conditions = {
            "ground_condition": "",
            "lighting_condition": lighting,
            "evidence_note": evidence_note,
        }
        environmental_data = {"evidence_note": evidence_note}

        zones = db.query(Zone).filter(Zone.site_id == site_id).all()
        zone_data = [
            {
                "zone_id": z.id,
                "zone_name": z.name,
                "risk_level": "LOW",
                "active_hazard_count": 0,
            }
            for z in zones
        ]

        equipment = _video_equipment(report)
        equipment_data = [dict(e, nearby_worker_count=worker_count) for e in equipment]
        worker_ppe = list((report.get("ppe_workers") or {}).get("workers", []))

        # ── Risk agent (site risk & hazard intelligence) ────────────────────
        from app.agents.site_risk_agent.agent import SiteRiskAgent

        risk_result = SiteRiskAgent().analyze_site(
            event_data={
                "detected_objects": detected_objects,
                "worker_count": worker_count,
                "equipment_activity": {
                    e["name"]: {"status": e["status"], "activity": e["activity"]}
                    for e in equipment
                },
            },
            equipment_data=equipment_data,
            environmental_data=environmental_data,
            site_conditions=site_conditions,
            detected_objects=detected_objects,
        )

        # ── Safety agent (PPE compliance, worker protection) ───────────────
        from app.agents.safety_agent.agent import SafetyAgent

        safety_result = SafetyAgent().analyze_site(
            worker_ppe=worker_ppe,
            equipment_data=equipment_data,
            detected_objects=detected_objects,
            site_conditions=site_conditions,
            zone_data=zone_data,
            ppe_source="ppe_detection",
            video_accident_zones=report.get("accident_zones"),
        )

        # ── Persist evidence, all tagged with the SAME analysis_id ─────────
        db.query(Equipment).filter(Equipment.site_id == site_id).delete()
        for eq in equipment:
            db.add(Equipment(
                id=str(uuid.uuid4()),
                site_id=site_id,
                analysis_id=analysis_id,
                name=eq["name"],
                equipment_type=eq["equipment_type"],
                status="active",
                zone_id=None,
                activity=eq["activity"],
                operating_duration_minutes=0,
                maintenance_status="operational",
                nearby_worker_count=worker_count,
                last_updated=now,
            ))

        db.query(Worker).filter(Worker.site_id == site_id).delete()
        worker_rows: List[Dict[str, Any]] = []
        for w in worker_ppe:
            worker_key = str(w.get("worker_id") or f"w{len(worker_rows) + 1}").lower()
            wid = "wrk_" + re.sub(r"\W", "", worker_key)
            row = Worker(
                id=wid,
                site_id=site_id,
                analysis_id=analysis_id,
                name=f"Worker {worker_key}",
                role=w.get("worker_role", "worker"),
                zone_id=None,
                ppe_status=w.get("ppe_status", "compliant"),
                missing_ppe=w.get("missing_ppe", []),
                detected_ppe=w.get("detected_ppe", []),
                is_present=1,
                last_seen=now,
            )
            db.add(row)
            worker_rows.append({
                "worker_id": wid,
                "worker_name": row.name,
                "worker_role": row.role,
                "ppe_status": row.ppe_status,
                "detected_ppe": row.detected_ppe,
                "missing_ppe": row.missing_ppe,
            })

        event = MonitoringEvent(
            id=str(uuid.uuid4()),
            site_id=site_id,
            analysis_id=analysis_id,
            zone_id=None,
            event_type="video_analysis",
            source="computer_vision",
            detected_objects=detected_objects,
            equipment_activity={
                e["name"]: {"status": e["status"], "activity": e["activity"]}
                for e in equipment
            },
            environmental_conditions=environmental_data,
            site_conditions=site_conditions,
            raw_data={
                "frames_analyzed": report.get("frames_analyzed", 0),
                "lighting_condition": lighting,
                "evidence_note": evidence_note,
            },
            description=(
                f"Video analysis: {worker_count} worker(s), "
                f"{report.get('vehicle_count', 0)} vehicle(s) across "
                f"{report.get('frames_analyzed', 0)} sampled frame(s)"
            ),
            timestamp=now,
        )
        db.add(event)

        rd = risk_result["risk_assessment"]
        risk_assessment = RiskAssessment(
            id=str(uuid.uuid4()),
            site_id=site_id,
            analysis_id=analysis_id,
            timestamp=now,
            overall_score=rd["overall_score"],
            risk_level=rd["risk_level"],
            environmental_score=rd["environmental_score"],
            equipment_score=rd["equipment_score"],
            site_condition_score=rd["site_condition_score"],
            activity_score=rd["activity_score"],
            environmental_factors=rd["environmental_factors"],
            equipment_factors=rd["equipment_factors"],
            site_condition_factors=rd["site_condition_factors"],
            activity_factors=rd["activity_factors"],
            summary=rd["summary"],
        )
        db.add(risk_assessment)
        db.flush()

        hazard_ids: List[str] = []
        for h in risk_result["hazards"]:
            hazard = Hazard(
                id=str(uuid.uuid4()),
                site_id=site_id,
                analysis_id=analysis_id,
                zone_id=None,
                hazard_type=h.get("hazard_type", "unknown"),
                description=h.get("description", ""),
                severity=_SEVERITY_MAP.get(str(h.get("severity", "medium")).lower(), "MEDIUM"),
                risk_contribution=h.get("risk_contribution", 0),
                evidence=h.get("evidence", ""),
                source=h.get("source", "video_vision"),
                recommended_mitigation=h.get("recommended_mitigation", ""),
                status="detected",
                timestamp=now,
            )
            db.add(hazard)
            db.flush()
            hazard_ids.append(hazard.id)
            db.add(RiskAssessmentHazard(
                id=str(uuid.uuid4()),
                risk_assessment_id=risk_assessment.id,
                hazard_id=hazard.id,
            ))

        for i, rec in enumerate(risk_result["recommendations"]):
            db.add(Recommendation(
                id=str(uuid.uuid4()),
                risk_assessment_id=risk_assessment.id,
                site_id=site_id,
                analysis_id=analysis_id,
                title=rec.get("title", ""),
                description=rec.get("description", ""),
                priority=rec.get("priority", "MEDIUM"),
                hazard_type=rec.get("hazard_type", ""),
                related_hazard_id=hazard_ids[i] if i < len(hazard_ids) else None,
                status="pending",
                created_at=now,
            ))

        violation_seed: List[Dict[str, Any]] = []
        for h in safety_result.get("hazards", []):
            violation = SafetyViolation(
                id=str(uuid.uuid4()),
                site_id=site_id,
                analysis_id=analysis_id,
                zone_id=None,
                worker_id=None,
                violation_type=h.get("hazard_type", "unsafe_behavior"),
                description=h.get("description", ""),
                severity=_SEVERITY_MAP.get(str(h.get("severity", "medium")).lower(), "MEDIUM"),
                risk_contribution=h.get("risk_contribution", 0),
                recommended_mitigation=h.get("recommended_mitigation", ""),
                status="open",
                source=h.get("source", "video_vision"),
                timestamp=now,
            )
            db.add(violation)
            violation_seed.append({"status": "open", "severity": violation.severity})

        for v in safety_result.get("ppe_compliance", {}).get("violations", []):
            violation = SafetyViolation(
                id=str(uuid.uuid4()),
                site_id=site_id,
                analysis_id=analysis_id,
                zone_id=None,
                worker_id=None,
                violation_type="ppe_violation",
                description=(
                    f"{v.get('worker_id')} missing "
                    f"{', '.join(v.get('missing_ppe', []) or ['PPE'])}"
                ),
                severity="HIGH",
                risk_contribution=35.0,
                recommended_mitigation="Issue replacement PPE and enforce compliance",
                status="open",
                source="ppe_detection",
                timestamp=now,
            )
            db.add(violation)
            violation_seed.append({"status": "open", "severity": violation.severity})

        ppe_res = safety_result["ppe_compliance"]
        alerts = build_safety_alerts(
            violation_seed + [
                {"status": "open", "severity": h.get("severity", "LOW")}
                for h in safety_result.get("hazards", [])
            ],
            ppe_res.get("compliance_rate", 1.0),
            safety_result.get("overall_safety_level", "LOW"),
        )
        alert_rows = []
        for a in alerts:
            alert = SafetyAlert(
                id=str(uuid.uuid4()),
                site_id=site_id,
                analysis_id=analysis_id,
                zone_id=None,
                alert_type=a["alert_type"],
                message=a["message"],
                severity=a["severity"],
                is_acknowledged=0,
                timestamp=now,
            )
            db.add(alert)
            alert_rows.append(a)

        worker_res = safety_result["worker_safety"]
        accident_res = safety_result.get("accident_zones", {}).get("overall_accident_risk", {})
        safety_assessment = SafetyAssessment(
            id=str(uuid.uuid4()),
            site_id=site_id,
            analysis_id=analysis_id,
            timestamp=now,
            overall_safety_score=safety_result["overall_safety_score"],
            overall_safety_level=safety_result["overall_safety_level"],
            ppe_score=ppe_res.get("score", 0),
            ppe_compliance_rate=ppe_res.get("compliance_rate", 1.0),
            worker_safety_score=worker_res.get("score", 0),
            worker_count=len(worker_rows),
            accident_zone_score=accident_res.get("score", 0),
            ppe_factors=ppe_res.get("factors", []),
            worker_factors=worker_res.get("factors", []),
            accident_factors=accident_res.get("factors", []),
            violation_count=len(violation_seed),
            alert_count=len(alert_rows),
            summary=safety_result.get("summary", ""),
        )
        db.add(safety_assessment)

        # ── Milestone 3 · Compliance & Insurance agents ─────────────────────
        from app.services.compliance_baseline import (
            ensure_compliance_baseline,
            site_compliance_baseline,
        )

        ensure_compliance_baseline(db, site_id)
        reqs, insp_ctx = site_compliance_baseline(db, site_id)

        m3_context: Dict[str, Any] = {
            "site_id": site_id,
            "analysis_id": analysis_id,
            "timestamp": now,
            "requirements": reqs,
            "inspections": insp_ctx,
            "violations": [
                {
                    "violation_type": h.get("hazard_type", "violation"),
                    "description": h.get("description", ""),
                    "severity": _SEVERITY_MAP.get(str(h.get("severity", "medium")).lower(), "MEDIUM"),
                    "status": "open",
                    "source": h.get("source", "video_vision"),
                }
                for h in safety_result.get("hazards", [])
            ] + [
                {
                    "violation_type": "ppe_violation",
                    "description": (
                        f"{v.get('worker_id', 'Worker')} missing "
                        f"{', '.join(v.get('missing_ppe', []) or ['PPE'])}"
                    ),
                    "severity": "HIGH",
                    "status": "open",
                    "source": "ppe_detection",
                }
                for v in ppe_res.get("violations", [])
            ],
            "hazards": list(risk_result["hazards"]) + list(safety_result.get("hazards", [])),
            "worker_ppe": worker_ppe,
            "safety": safety_result,
            "risk": risk_result,
            "alerts": alert_rows,
            "accident_zones": report.get("accident_zones"),
            "equipment": equipment_data,
            "site_conditions": site_conditions,
            "video": {"video_source": Path(path).name, "lighting_condition": lighting},
        }

        from app.agents.compliance_agent import ComplianceAgent
        from app.agents.insurance_agent import InsuranceAgent

        compliance_result = ComplianceAgent().analyze_site(m3_context)
        insurance_result = InsuranceAgent().analyze_site(
            {**m3_context, "compliance": compliance_result}
        )

        for f in compliance_result["findings"]:
            db.add(ComplianceFinding(
                id=f["id"],
                site_id=site_id,
                analysis_id=analysis_id,
                requirement_id=f.get("requirement_id"),
                category=f.get("category", ""),
                requirement=f.get("requirement", ""),
                description=f.get("description", ""),
                status=f.get("status", "NOT_VERIFIED"),
                severity=f.get("severity", "MEDIUM"),
                evidence=f.get("evidence", ""),
                evidence_meta=f.get("evidence_meta", {}),
                source=f.get("source", "video_vision"),
                timestamp=(
                    datetime.fromisoformat(f["timestamp"].replace("Z", "+00:00"))
                    if isinstance(f.get("timestamp"), str)
                    else (f.get("timestamp") or now)
                ),
            ))

        by_req_id = {f.get("requirement_id"): f for f in compliance_result["findings"]}
        for req_row in db.query(ComplianceRequirement).filter(
            ComplianceRequirement.site_id == site_id
        ).all():
            find = by_req_id.get(req_row.id)
            if find:
                req_row.status = find["status"]
                req_row.evidence = find.get("evidence", "")
                req_row.last_checked = now

        by_type = {
            insp["inspection_type"]: insp
            for insp in compliance_result["inspections"]["inspections"]
        }
        for insp_row in db.query(InspectionRecord).filter(
            InspectionRecord.site_id == site_id
        ).all():
            tracked = by_type.get(insp_row.inspection_type)
            if tracked:
                insp_row.status = tracked["status"]
                insp_row.evidence = tracked.get("evidence", "")
                insp_row.last_inspection = None

        cr = compliance_result
        compliance_assessment = ComplianceAssessment(
            id=str(uuid.uuid4()),
            site_id=site_id,
            analysis_id=analysis_id,
            timestamp=now,
            overall_score=cr.get("overall_score"),
            compliance_level=cr.get("compliance_level"),
            category_scores=cr.get("category_scores", {}),
            requirements_checked=cr.get("requirements_checked", 0),
            compliant_count=cr.get("compliant_count", 0),
            non_compliant_count=cr.get("non_compliant_count", 0),
            not_verified_count=cr.get("not_verified_count", 0),
            open_violations=cr.get("open_violations", 0),
            overdue_inspections=(compliance_result.get("inspections") or {}).get("overdue", 0),
            evidence_available=1 if cr.get("evidence_available") else 0,
            score_basis=cr.get("score_basis", ""),
            summary=cr.get("summary", ""),
            recommendations=cr.get("recommendations", []),
            report=cr.get("report", {}),
        )
        db.add(compliance_assessment)

        for inc in insurance_result.get("incidents", []):
            inc_ts = inc.get("timestamp", now)
            if isinstance(inc_ts, str):
                try:
                    inc_ts = datetime.fromisoformat(inc_ts.replace("Z", "+00:00"))
                except ValueError:
                    inc_ts = now
            db.add(InsuranceIncident(
                id=str(uuid.uuid4()),
                site_id=site_id,
                analysis_id=analysis_id,
                incident_type=inc.get("incident_type", ""),
                description=inc.get("description", ""),
                severity=inc.get("severity", "LOW"),
                timestamp=inc_ts,
                workers_involved=[{"count": inc.get("affected_workers", 0)}],
                hazards=inc.get("evidence", []),
                violations=[],
                evidence=inc.get("evidence", []),
                claim_risk=(inc.get("severity_details") or {}).get("severity_level", "LOW"),
            ))

        for doc in (insurance_result.get("claim_documentation") or {}).get("documents", []):
            db.add(ClaimRecord(
                id=doc.get("document_id", str(uuid.uuid4())),
                site_id=site_id,
                analysis_id=analysis_id,
                incident_id=doc.get("incident_id"),
                status="DRAFTED",
                claim_summary=doc.get("description", ""),
                documentation=[doc],
                created_at=now,
            ))

        ir = insurance_result
        db.add(InsuranceAssessment(
            id=str(uuid.uuid4()),
            site_id=site_id,
            analysis_id=analysis_id,
            timestamp=now,
            risk_score=ir.get("insurance_risk_score", 0),
            risk_level=ir.get("risk_level", "LOW"),
            exposure=ir.get("exposure", {}),
            claim_risk=ir.get("claim_risk", {}),
            open_incidents=ir.get("incident_count", 0),
            incident_severity=ir.get("incident_severity", "LOW"),
            factors=ir.get("risk_factors", []),
            evidence=(ir.get("claim_risk") or {}).get("evidence", []),
            summary=ir.get("summary", ""),
            recommendations=ir.get("recommendations", []),
        ))

        for z in zones:
            z.current_risk_score = rd["overall_score"]
            z.risk_level = rd["risk_level"]

        analysis.status = "completed"
        analysis.worker_count = worker_count
        analysis.vehicle_count = report.get("vehicle_count", 0)
        analysis.helmet_violations = report.get("helmet_violations", 0)
        analysis.vest_violations = report.get("vest_violations", 0)
        analysis.other_violations = report.get("other_violations", 0)
        analysis.total_violations = report.get("total_violations", 0)
        analysis.ppe_compliance = report.get("ppe_compliance", 100.0)
        analysis.detected_objects = detected_objects
        analysis.ppe_workers = report.get("ppe_workers", {})
        analysis.frames_analyzed = report.get("frames_analyzed", 0)
        analysis.model_used = report.get("model_used", "yolov8n.pt")
        if meta is not None:
            analysis.duration_seconds = meta.duration_seconds
            analysis.fps = meta.fps
            analysis.width = meta.width
            analysis.height = meta.height
            analysis.frame_count = meta.frame_count
        analysis.evidence = {
            "lighting_condition": lighting,
            "evidence_note": evidence_note,
            "frame_evidence": report.get("frame_evidence", []),
            "accident_zones": report.get("accident_zones", {}),
        }

        db.commit()
        db.refresh(analysis)

        # Milestone 4: raise evidence-based risk alerts. Uses ONLY the real,
        # persisted results of this run. Never allowed to fail the analysis.
        try:
            evaluate_analysis(
                db,
                site_id,
                analysis_id,
                risk=_risk_summary(rd),
                safety=_safety_summary(safety_result),
                alerts=[
                    {
                        "id": a.id,
                        "message": a.message,
                        "severity": a.severity,
                        "zone_id": a.zone_id,
                    }
                    for a in db.query(SafetyAlert)
                    .filter(SafetyAlert.analysis_id == analysis_id).all()
                ],
                violations=[
                    {
                        "id": v.id,
                        "violation_type": v.violation_type,
                        "description": v.description,
                        "severity": v.severity,
                        "worker_id": v.worker_id,
                        "zone_id": v.zone_id,
                    }
                    for v in db.query(SafetyViolation)
                    .filter(SafetyViolation.analysis_id == analysis_id).all()
                ],
                hazards=[
                    {
                        "id": h.id,
                        "description": h.description or h.hazard_type,
                        "hazard_type": h.hazard_type,
                        "severity": h.severity,
                        "zone_id": h.zone_id,
                    }
                    for h in db.query(Hazard)
                    .filter(Hazard.analysis_id == analysis_id).all()
                ],
                incidents=[
                    {
                        "id": inc.id,
                        "description": inc.description,
                        "severity": inc.severity,
                    }
                    for inc in db.query(InsuranceIncident)
                    .filter(InsuranceIncident.analysis_id == analysis_id).all()
                ],
            )
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception(
                "notification evaluation failed for analysis %s", analysis_id
            )

        return build_analysis_response(db, analysis, extra={
            "event_id": event.id,
            "compliance": compliance_result,
            "insurance": insurance_result,
            "safety": _safety_summary(safety_result),
            "risk": _risk_summary(rd),
        })
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        analysis = db.query(VideoAnalysis).filter(VideoAnalysis.id == analysis_id).first()
        if analysis is not None:
            analysis.status = "failed"
            analysis.error = str(exc)
            db.commit()
        return {"status": "failed", "analysis_id": analysis_id, "error": str(exc)}


def _safety_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    ppe = result.get("ppe_compliance", {})
    worker = result.get("worker_safety", {})
    accident = result.get("accident_zones", {}).get("overall_accident_risk", {})
    return {
        "overall_safety_score": result.get("overall_safety_score", 0),
        "overall_safety_level": result.get("overall_safety_level", "LOW"),
        "ppe_score": ppe.get("score", 0),
        "ppe_compliance_rate": ppe.get("compliance_rate", 1.0),
        "compliant_count": ppe.get("compliant_count", 0),
        "non_compliant_count": ppe.get("non_compliant_count", 0),
        "worker_safety_score": worker.get("score", 0),
        "accident_zone_score": accident.get("score", 0),
        "violations": result.get("hazards", []),
        "unsafe_behavior_events": result.get("unsafe_behavior_events", []),
        "recommendations": result.get("recommendations", []),
        "summary": result.get("summary", ""),
    }


def _risk_summary(rd: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "overall_score": rd.get("overall_score", 0),
        "risk_level": rd.get("risk_level", "LOW"),
        "environmental_score": rd.get("environmental_score", 0),
        "equipment_score": rd.get("equipment_score", 0),
        "site_condition_score": rd.get("site_condition_score", 0),
        "activity_score": rd.get("activity_score", 0),
        "environmental_factors": rd.get("environmental_factors", []),
        "equipment_factors": rd.get("equipment_factors", []),
        "site_condition_factors": rd.get("site_condition_factors", []),
        "activity_factors": rd.get("activity_factors", []),
        "summary": rd.get("summary", ""),
    }


def build_analysis_response(
    db: Session,
    analysis: VideoAnalysis,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble the full per-analysis payload from the stored (persisted) rows."""
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
    hazards = db.query(Hazard).filter(Hazard.analysis_id == analysis.id).order_by(Hazard.timestamp.desc()).all()
    recommendations = (
        db.query(Recommendation)
        .filter(Recommendation.analysis_id == analysis.id)
        .order_by(Recommendation.created_at.desc())
        .all()
    )
    equipment = db.query(Equipment).filter(Equipment.analysis_id == analysis.id).all()
    workers = db.query(Worker).filter(Worker.analysis_id == analysis.id).all()
    violations = (
        db.query(SafetyViolation)
        .filter(SafetyViolation.analysis_id == analysis.id)
        .order_by(SafetyViolation.timestamp.desc())
        .all()
    )
    alerts = (
        db.query(SafetyAlert)
        .filter(SafetyAlert.analysis_id == analysis.id)
        .order_by(SafetyAlert.timestamp.desc())
        .all()
    )
    events = db.query(MonitoringEvent).filter(MonitoringEvent.analysis_id == analysis.id).order_by(MonitoringEvent.timestamp.desc()).all()

    evidence = analysis.evidence if isinstance(analysis.evidence, dict) else {}
    ppe_workers = analysis.ppe_workers if isinstance(analysis.ppe_workers, dict) else {}

    payload: Dict[str, Any] = {
        "status": analysis.status,
        "error": analysis.error,
        "analysis_id": analysis.id,
        "site_id": analysis.site_id,
        "timestamp": analysis.timestamp.isoformat() if analysis.timestamp else None,
        "video": {
            "filename": analysis.original_filename,
            "path": analysis.stored_path,
            "source_type": analysis.source_type,
            "duration_seconds": analysis.duration_seconds,
            "fps": analysis.fps,
            "width": analysis.width,
            "height": analysis.height,
            "frame_count": analysis.frame_count,
            "frames_analyzed": analysis.frames_analyzed,
            "frame_interval": analysis.frame_interval,
            "model_used": analysis.model_used,
            "lighting_condition": evidence.get("lighting_condition", ""),
        },
        "evidence_note": evidence.get(
            "evidence_note",
            "Environmental dimensions not available from current video evidence.",
        ),
        "accident_zones": evidence.get("accident_zones", {}),
        "detected_objects": analysis.detected_objects,
        "frame_evidence": [
            dict(f, analysis_id=analysis.id)
            for f in evidence.get("frame_evidence", [])
        ],
        "worker_count": analysis.worker_count,
        "vehicle_count": analysis.vehicle_count,
        "ppe": {
            "compliance": analysis.ppe_compliance,
            "total_violations": analysis.total_violations,
            "helmet_violations": analysis.helmet_violations,
            "vest_violations": analysis.vest_violations,
            "other_violations": analysis.other_violations,
            "workers": ppe_workers.get("workers", []),
        },
        "equipment": [
            {
                "id": e.id,
                "name": e.name,
                "equipment_type": e.equipment_type,
                "status": e.status,
                "activity": e.activity,
                "nearby_worker_count": e.nearby_worker_count,
            }
            for e in equipment
        ],
"workers": [
        {
            "id": w.id,
            "analysis_id": w.analysis_id,
            "name": w.name,
                "role": w.role,
                "ppe_status": w.ppe_status,
                "missing_ppe": w.missing_ppe,
                "detected_ppe": w.detected_ppe,
            }
            for w in workers
        ],
        "risk": _risk_summary(
            {
                "overall_score": risk.overall_score if risk else 0,
                "risk_level": risk.risk_level if risk else "LOW",
                "environmental_score": risk.environmental_score if risk else 0,
                "equipment_score": risk.equipment_score if risk else 0,
                "site_condition_score": risk.site_condition_score if risk else 0,
                "activity_score": risk.activity_score if risk else 0,
                "environmental_factors": risk.environmental_factors if risk else [],
                "equipment_factors": risk.equipment_factors if risk else [],
                "site_condition_factors": risk.site_condition_factors if risk else [],
                "activity_factors": risk.activity_factors if risk else [],
                "summary": risk.summary if risk else "",
            }
        ),
    }

    if safety is not None:
        compliant = sum(1 for w in workers if w.ppe_status == "compliant")
        non_compliant = sum(1 for w in workers if w.ppe_status != "compliant")
        payload["safety"] = {
            "evidence_available": len(workers) > 0,
            "overall_safety_score": safety.overall_safety_score,
            "overall_safety_level": safety.overall_safety_level,
            "ppe_score": safety.ppe_score,
            "ppe_compliance_rate": safety.ppe_compliance_rate,
            "worker_safety_score": safety.worker_safety_score,
            "worker_count": safety.worker_count,
            "accident_zone_score": safety.accident_zone_score,
            "ppe_factors": safety.ppe_factors,
            "worker_factors": safety.worker_factors,
            "accident_factors": safety.accident_factors,
            "violation_count": safety.violation_count,
            "alert_count": safety.alert_count,
            "summary": safety.summary,
            "ppe_compliance": {
                "score": safety.ppe_score,
                "compliance_rate": safety.ppe_compliance_rate,
                "compliant_count": compliant,
                "non_compliant_count": non_compliant,
                "workers_assessed": len(workers),
                "violations": [
                    {
                        "worker_id": v.id,
                        "missing_ppe": v.missing_ppe or [],
                        "severity": "HIGH",
                    }
                    for v in workers
                    if v.ppe_status != "compliant"
                ],
            },
        }
    else:
        payload["safety"] = {
            "overall_safety_score": 0,
            "overall_safety_level": "LOW",
            "summary": "No safety assessment for this analysis.",
        }

    payload["hazards"] = [
        {
            "id": h.id,
            "analysis_id": h.analysis_id,
            "hazard_type": h.hazard_type,
            "description": h.description,
            "severity": h.severity,
            "risk_contribution": h.risk_contribution,
            "evidence": h.evidence,
            "source": h.source,
            "recommended_mitigation": h.recommended_mitigation,
            "timestamp": h.timestamp.isoformat() if h.timestamp else None,
        }
        for h in hazards
    ]
    payload["recommendations"] = [
        {
            "id": r.id,
            "analysis_id": r.analysis_id,
            "title": r.title,
            "description": r.description,
            "priority": r.priority,
            "hazard_type": r.hazard_type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recommendations
    ]
    payload["violations"] = [
        {
            "id": v.id,
            "analysis_id": v.analysis_id,
            "violation_type": v.violation_type,
            "description": v.description,
            "severity": v.severity,
            "status": v.status,
            "source": v.source,
            "timestamp": v.timestamp.isoformat() if v.timestamp else None,
        }
        for v in violations
    ]
    payload["alerts"] = [
        {
            "id": a.id,
            "analysis_id": a.analysis_id,
            "alert_type": a.alert_type,
            "message": a.message,
            "severity": a.severity,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        }
        for a in alerts
    ]
    payload["events"] = [
        {
            "id": e.id,
            "analysis_id": e.analysis_id,
            "event_type": e.event_type,
            "source": e.source,
            "description": e.description,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in events
    ]

    if extra:
        payload.update(extra)
    return payload


def get_latest_analysis(db: Session, site_id: str) -> Optional[VideoAnalysis]:
    return (
        db.query(VideoAnalysis)
        .filter(VideoAnalysis.site_id == site_id)
        .order_by(VideoAnalysis.timestamp.desc())
        .first()
    )