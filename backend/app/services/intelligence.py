"""Construction Risk Intelligence Engine (Milestone 4 - Reporting Intelligence).

A read/aggregation layer over the PERSISTED analysis rows produced by the
M1-M3 pipeline. It never re-runs YOLO or any model and NEVER computes new
scores: every figure, level and fact surfaced in the unified intelligence
context comes straight from the stored ``VideoAnalysis``, ``RiskAssessment``,
``SafetyAssessment``, ``ComplianceAssessment``, ``InsuranceAssessment``,
``Hazard``, ``SafetyViolation``, ``SafetyAlert``, ``Worker``, ``Equipment``,
``Recommendation``, ``ComplianceFinding``, ``InsuranceIncident`` and
``ClaimRecord`` rows for ONE ``analysis_id``.

Missing evidence is reported as ``NOT_AVAILABLE`` / ``INSUFFICIENT_DATA``,
never invented.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.models import (
    ClaimRecord,
    ComplianceAssessment,
    ComplianceFinding,
    Equipment,
    Hazard,
    InspectionRecord,
    InsuranceAssessment,
    InsuranceIncident,
    Recommendation,
    RiskAssessment,
    SafetyAlert,
    SafetyAssessment,
    SafetyViolation,
    Site,
    VideoAnalysis,
    Worker,
    Zone,
)
from app.services.notification_service import evaluate_analysis

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class IntelligenceError(Exception):
    """Base error raised by the intelligence engine."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class SiteNotFoundError(IntelligenceError):
    pass


class AnalysisNotFoundError(IntelligenceError):
    pass


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


def _sev(value: Any) -> str:
    level = str(value or "LOW").upper()
    if level not in _SEVERITY_RANK:
        return "LOW"
    return level


def _level(value: Any) -> str:
    """Normalise a risk level value to a known band, or NOT_AVAILABLE."""
    level = str(value or "").upper()
    if level in _SEVERITY_RANK:
        return level
    return "NOT_AVAILABLE"


def _num(value: Any, default: Any = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rollup_by_severity(rows: list[dict], key: str = "severity") -> dict:
    out = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for row in rows:
        level = _sev(row.get(key))
        out[level] = out.get(level, 0) + 1
    return out


def _sort_by_severity(rows: list[dict], key: str = "severity") -> list[dict]:
    return sorted(
        rows, key=lambda r: _SEVERITY_RANK.get(_sev(r.get(key)), 0), reverse=True
    )


def _zone_map(db: Session, site_id: str) -> dict:
    return {z.id: z.name for z in db.query(Zone).filter(Zone.site_id == site_id).all()}


def _worker_map(db: Session, site_id: str, analysis_id: str) -> dict:
    workers = db.query(Worker).filter(
        Worker.site_id == site_id, Worker.analysis_id == analysis_id
    ).all()
    return {w.id: w for w in workers}


def _hazard_to_dict(h: Hazard, zones: dict) -> dict:
    return {
        "id": h.id,
        "hazard_type": h.hazard_type,
        "description": h.description,
        "severity": _sev(h.severity),
        "risk_contribution": h.risk_contribution,
        "zone_id": h.zone_id,
        "zone_name": zones.get(h.zone_id),
        "evidence": h.evidence or "",
        "status": h.status,
        "timestamp": _iso(h.timestamp),
    }


def _violation_to_dict(v: SafetyViolation, zones: dict, workers: dict) -> dict:
    w = workers.get(v.worker_id)
    return {
        "id": v.id,
        "violation_type": v.violation_type,
        "description": v.description,
        "severity": _sev(v.severity),
        "risk_contribution": v.risk_contribution,
        "recommended_mitigation": v.recommended_mitigation or "",
        "status": v.status,
        "worker_id": v.worker_id,
        "worker_name": w.name if w else "",
        "zone_id": v.zone_id,
        "zone_name": zones.get(v.zone_id),
        "timestamp": _iso(v.timestamp),
    }


def _alert_to_dict(a: SafetyAlert, zones: dict) -> dict:
    return {
        "id": a.id,
        "alert_type": a.alert_type,
        "message": a.message,
        "severity": _sev(a.severity),
        "zone_id": a.zone_id,
        "zone_name": zones.get(a.zone_id),
        "acknowledged": bool(a.is_acknowledged),
        "timestamp": _iso(a.timestamp),
    }


def _incident_to_dict(i: InsuranceIncident) -> dict:
    return {
        "id": i.id,
        "incident_type": i.incident_type,
        "description": i.description,
        "severity": _sev(i.severity),
        "claim_risk": _level(i.claim_risk),
        "workers_involved": i.workers_involved or [],
        "hazards": i.hazards or [],
        "violations": i.violations or [],
        "timestamp": _iso(i.timestamp),
    }


def _worker_to_dict(w: Worker, zones: dict) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "role": w.role,
        "ppe_status": w.ppe_status or "unknown",
        "missing_ppe": w.missing_ppe or [],
        "detected_ppe": w.detected_ppe or [],
        "zone_id": w.zone_id,
        "zone_name": zones.get(w.zone_id),
        "is_present": bool(w.is_present),
    }


def _equipment_to_dict(e: Equipment, zones: dict) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "equipment_type": e.equipment_type,
        "status": e.status,
        "activity": e.activity,
        "maintenance_status": e.maintenance_status,
        "operating_duration_minutes": e.operating_duration_minutes,
        "nearby_worker_count": e.nearby_worker_count,
        "zone_id": e.zone_id,
        "zone_name": zones.get(e.zone_id),
    }


def _recommendation_to_dict(r: Recommendation) -> dict:
    return {
        "source": "site_risk_agent",
        "id": r.id,
        "title": r.title,
        "description": r.description,
        "priority": str(r.priority or "medium").upper(),
        "hazard_type": r.hazard_type,
        "status": r.status,
        "analysis_id": r.analysis_id,
    }


def _finding_to_dict(f: ComplianceFinding) -> dict:
    return {
        "id": f.id,
        "category": f.category,
        "requirement": f.requirement,
        "description": f.description,
        "status": _level(f.status),
        "severity": _sev(f.severity),
        "evidence": f.evidence,
        "evidence_meta": f.evidence_meta or {},
        "timestamp": _iso(f.timestamp),
    }


class IntelligenceEngine:
    """Assemble the unified, evidence-traced intelligence context for an analysis."""

    def build(self, db: Session, site_id: str, analysis_id: str) -> dict:
        site = db.query(Site).filter(Site.id == site_id).first()
        if site is None:
            raise SiteNotFoundError(f"Site {site_id} does not exist.")

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
                f"Analysis {analysis_id} not found for site {site_id}."
            )

        # ── M1-M3 persisted results for THIS analysis only ─────────────────
        risk = (
            db.query(RiskAssessment)
            .filter(RiskAssessment.analysis_id == analysis_id)
            .order_by(RiskAssessment.timestamp.desc())
            .first()
        )
        safety = (
            db.query(SafetyAssessment)
            .filter(SafetyAssessment.analysis_id == analysis_id)
            .order_by(SafetyAssessment.timestamp.desc())
            .first()
        )
        compliance = (
            db.query(ComplianceAssessment)
            .filter(ComplianceAssessment.analysis_id == analysis_id)
            .order_by(ComplianceAssessment.timestamp.desc())
            .first()
        )
        insurance = (
            db.query(InsuranceAssessment)
            .filter(InsuranceAssessment.analysis_id == analysis_id)
            .order_by(InsuranceAssessment.timestamp.desc())
            .first()
        )

        hazards = (
            db.query(Hazard).filter(Hazard.analysis_id == analysis_id).all()
        )
        violations = (
            db.query(SafetyViolation)
            .filter(SafetyViolation.analysis_id == analysis_id)
            .order_by(SafetyViolation.timestamp.desc())
            .all()
        )
        alerts = (
            db.query(SafetyAlert)
            .filter(SafetyAlert.analysis_id == analysis_id)
            .order_by(SafetyAlert.timestamp.desc())
            .all()
        )
        workers = (
            db.query(Worker).filter(Worker.analysis_id == analysis_id).all()
        )
        equipment = (
            db.query(Equipment).filter(Equipment.analysis_id == analysis_id).all()
        )
        recommendations = (
            db.query(Recommendation)
            .filter(Recommendation.analysis_id == analysis_id)
            .all()
        )
        findings = (
            db.query(ComplianceFinding)
            .filter(ComplianceFinding.analysis_id == analysis_id)
            .all()
        )
        incidents = (
            db.query(InsuranceIncident)
            .filter(InsuranceIncident.analysis_id == analysis_id)
            .all()
        )
        claims = (
            db.query(ClaimRecord).filter(ClaimRecord.analysis_id == analysis_id).all()
        )
        inspections = (
            db.query(InspectionRecord).filter(InspectionRecord.site_id == site_id).all()
        )

        zones = _zone_map(db, site_id)
        workers_by_id = {w.id: w for w in workers}

        hazard_rows = [_hazard_to_dict(h, zones) for h in hazards]
        violation_rows = [_violation_to_dict(v, zones, workers_by_id) for v in violations]
        alert_rows = [_alert_to_dict(a, zones) for a in alerts]
        incident_rows = [_incident_to_dict(i) for i in incidents]
        worker_rows = [_worker_to_dict(w, zones) for w in workers]
        equipment_rows = [_equipment_to_dict(e, zones) for e in equipment]
        recommendation_rows = [_recommendation_to_dict(r) for r in recommendations]
        finding_rows = [_finding_to_dict(f) for f in findings]

        # ── Findings rollup (critical / high) — this analysis only ─────────
        def as_finding(kind: str, row: dict, extra: dict | None = None) -> dict:
            item = {
                "type": kind,
                "severity": _sev(row.get("severity")),
                "title": row.get("title")
                or row.get("violation_type")
                or row.get("hazard_type")
                or row.get("incident_type")
                or row.get("alert_type")
                or "Detected event",
                "description": row.get("description") or row.get("message") or "",
                "timestamp": row.get("timestamp"),
                "analysis_id": analysis_id,
            }
            if extra:
                item.update(extra)
            return item

        hazards_by_sev = _rollup_by_severity(hazard_rows)
        violations_by_sev = _rollup_by_severity(violation_rows)
        alerts_by_sev = _rollup_by_severity(alert_rows)
        incidents_by_sev = _rollup_by_severity(incident_rows)

        critical_findings: list[dict] = []
        high_findings: list[dict] = []

        for row in hazard_rows:
            level = _sev(row.get("severity"))
            item = as_finding("hazard", row, {"id": row["id"], "hazard_type": row["hazard_type"]})
            if level == "CRITICAL":
                critical_findings.append(item)
            elif level == "HIGH":
                high_findings.append(item)
        for row in violation_rows:
            level = _sev(row.get("severity"))
            item = as_finding(
                "violation", row,
                {"id": row["id"], "violation_type": row["violation_type"],
                 "worker_id": row["worker_id"], "worker_name": row["worker_name"],
                 "recommended_mitigation": row["recommended_mitigation"]},
            )
            if level == "CRITICAL":
                critical_findings.append(item)
            elif level == "HIGH":
                high_findings.append(item)
        for row in alert_rows:
            level = _sev(row.get("severity"))
            item = as_finding("safety_alert", row, {"id": row["id"], "alert_type": row["alert_type"]})
            if level == "CRITICAL":
                critical_findings.append(item)
            elif level == "HIGH":
                high_findings.append(item)
        for row in incident_rows:
            level = _sev(row.get("severity"))
            item = as_finding("incident", row, {"id": row["id"], "incident_type": row["incident_type"]})
            if level == "CRITICAL":
                critical_findings.append(item)
            elif level == "HIGH":
                high_findings.append(item)

        critical_findings = _sort_by_severity(critical_findings)
        high_findings = _sort_by_severity(high_findings)
        open_violations = [v for v in violation_rows if str(v["status"]).lower() == "open"]

        # ── Worker & PPE summary ───────────────────────────────────────────
        present_workers = [w for w in worker_rows if w["is_present"]]
        ppe_compliant = [w for w in present_workers if w["ppe_status"] == "compliant"]
        ppe_non_compliant = [
            w for w in present_workers
            if w["ppe_status"] not in ("compliant", "unknown")
        ]

        missing_ppe_entries = []
        for w in _sort_by_severity(
            [w for w in present_workers if w["missing_ppe"]], key="ppe_status"
        ):
            missing_ppe_entries.append({
                "worker_id": w["id"],
                "worker_name": w["name"],
                "role": w["role"],
                "missing_ppe": w["missing_ppe"],
            }) if w["missing_ppe"] else None

        violations_by_worker = {}
        for v in violation_rows:
            key = v.get("worker_id") or "(unknown)"
            violations_by_worker.setdefault(key, []).append(v)

        # ── Equipment summary ──────────────────────────────────────────────
        equipment_types: dict = {}
        for e in equipment_rows:
            equipment_types[str(e["equipment_type"]).upper()] = (
                equipment_types.get(str(e["equipment_type"]).upper(), 0) + 1
            )
        active_equipment = [e for e in equipment_rows if str(e["status"]).lower() == "active"]
        maintenance_issues = [
            e for e in equipment_rows
            if str(e["maintenance_status"]).lower() != "operational"
        ]

        # ── Compliance summary (from the persisted compliance assessment) ──
        compliance_data = None
        if compliance is not None:
            compliance_data = {
                "overall_score": compliance.overall_score,
                "compliance_level": _level(compliance.compliance_level),
                "requirements_checked": _int(compliance.requirements_checked),
                "compliant_count": _int(compliance.compliant_count),
                "non_compliant_count": _int(compliance.non_compliant_count),
                "not_verified_count": _int(compliance.not_verified_count),
                "open_violations": _int(compliance.open_violations),
                "overdue_inspections": _int(compliance.overdue_inspections),
                "evidence_available": _int(compliance.evidence_available),
                "score_basis": compliance.score_basis or "",
                "category_scores": (compliance.category_scores or {}),
                "summary": compliance.summary,
                "recommendations": compliance.recommendations or [],
                "report": {
                    k: v for k, v in (compliance.report or {}).items()
                },
            }

        # ── Insurance summary ──────────────────────────────────────────────
        insurance_data = None
        if insurance is not None:
            insurance_data = {
                "risk_score": _num(insurance.risk_score),
                "risk_level": _level(insurance.risk_level),
                "exposure": insurance.exposure or {},
                "claim_risk": insurance.claim_risk or {},
                "open_incidents": _int(insurance.open_incidents),
                "incident_severity": _sev(insurance.incident_severity),
                "factors": insurance.factors or [],
                "evidence": insurance.evidence or [],
                "summary": insurance.summary,
                "recommendations": insurance.recommendations or [],
            }

        # ── Recommendations (real persisted recommendation rows across agents)
        recs = []
        for r in recommendation_rows:
            recs.append(r)
        if compliance_data:
            for rec in compliance_data.get("recommendations", []):
                recs.append({
                    "source": "compliance_intelligence",
                    "id": None,
                    "title": rec.get("action", rec.get("title", "")) or rec.get("recommendation", ""),
                    "description": rec.get("description", rec.get("evidence", "")),
                    "priority": str(rec.get("priority", "MEDIUM")).upper(),
                    "category": rec.get("category", "compliance"),
                })
        if insurance_data:
            for rec in insurance_data.get("recommendations", []):
                recs.append({
                    "source": "insurance_intelligence",
                    "id": None,
                    "title": rec.get("action", rec.get("title", "")) or rec.get("recommendation", ""),
                    "description": rec.get("description", rec.get("evidence", "")),
                    "priority": str(rec.get("priority", "MEDIUM")).upper(),
                    "category": rec.get("category", "insurance"),
                })
        safety_mitigations = []
        for v in violation_rows:
            if v.get("recommended_mitigation"):
                safety_mitigations.append({
                    "source": "safety_intelligence",
                    "id": v["id"],
                    "title": v["recommended_mitigation"],
                    "description": f"{v['violation_type']} · {v.get('description', '')}",
                    "priority": _sev(v.get("severity")),
                    "hazard_type": v.get("violation_type"),
                    "worker_id": v.get("worker_id"),
                })
        recs.extend(safety_mitigations)

        priority_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        recs = sorted(
            recs, key=lambda r: priority_rank.get(str(r.get("priority", "MEDIUM")).upper(), 2)
        )

        # ── Data quality / availability ─────────────────────────────────────
        available_agents = {
            "site_risk": risk is not None,
            "safety": safety is not None,
            "compliance": compliance is not None,
            "insurance": insurance is not None,
        }

        overall_status = "COMPLETE" if risk and safety and compliance and insurance else "PARTIAL"

        # ── Evidence summary ────────────────────────────────────────────────
        evidence_summary = {
            "video": {
                "filename": analysis.original_filename or "",
                "source_type": analysis.source_type,
                "status": analysis.status,
                "duration_seconds": _num(analysis.duration_seconds),
                "fps": _num(analysis.fps),
                "frames_total": _int(analysis.frame_count),
                "frames_analyzed": _int(analysis.frames_analyzed),
                "frame_interval": _int(analysis.frame_interval),
                "model_used": analysis.model_used or "",
                "evidence_frames": _int((analysis.evidence or {}).get("frame_count", 0)),
            },
            "counts": {
                "hazards": len(hazard_rows),
                "safety_violations": len(violation_rows),
                "safety_alerts": len(alert_rows),
                "workers": len(worker_rows),
                "equipment": len(equipment_rows),
                "compliance_findings": len(finding_rows),
                "inspections": len(inspections),
                "insurance_incidents": len(incident_rows),
                "claim_records": len(claims),
                "recommendations_persisted": len(recommendation_rows),
            },
            "inspections": [
                {
                    "inspection_type": i.inspection_type,
                    "status": str(i.status or "NOT_AVAILABLE").upper(),
                    "due_date": _iso(i.due_date),
                    "last_inspection": _iso(i.last_inspection),
                    "evidence": i.evidence or "",
                }
                for i in inspections
            ],
        }

        data_quality = {
            "status": overall_status,
            "available_agents": available_agents,
            "insufficient_dimensions": [
                name for name, ok in available_agents.items() if not ok
            ],
            "note": (
                "All intelligence agents produced results for this analysis."
                if overall_status == "COMPLETE"
                else "One or more intelligence dimensions had no persisted result "
                "for this analysis; they are shown as NOT_AVAILABLE rather than guessed."
            ),
        }

        return {
            "status": overall_status,
            "analysis_id": analysis_id,
            "site_id": site_id,
            "site_name": site.name,
            "analysis_timestamp": _iso(analysis.timestamp),
            "video_source": {
                "filename": analysis.original_filename or "",
                "source_type": analysis.source_type,
                "duration_seconds": _num(analysis.duration_seconds),
                "fps": _num(analysis.fps),
                "frames_analyzed": _int(analysis.frames_analyzed),
                "model_used": analysis.model_used or "",
            },
            "overall_risk": {
                "score": risk.overall_score if risk else None,
                "level": _level(risk.risk_level if risk else None),
                "environmental_score": risk.environmental_score if risk else None,
                "equipment_score": risk.equipment_score if risk else None,
                "site_condition_score": risk.site_condition_score if risk else None,
                "activity_score": risk.activity_score if risk else None,
                "environmental_factors": (risk.environmental_factors or []) if risk else [],
                "equipment_factors": (risk.equipment_factors or []) if risk else [],
                "site_condition_factors": (risk.site_condition_factors or []) if risk else [],
                "activity_factors": (risk.activity_factors or []) if risk else [],
                "summary": (risk.summary or "") if risk else "",
            },
            "risk_level": _level(risk.risk_level if risk else None),
            "safety_summary": {
                "overall_safety_score": safety.overall_safety_score if safety else None,
                "overall_safety_level": _level(safety.overall_safety_level if safety else None),
                "ppe_score": safety.ppe_score if safety else None,
                "ppe_compliance_rate": safety.ppe_compliance_rate if safety else None,
                "worker_safety_score": safety.worker_safety_score if safety else None,
                "accident_zone_score": safety.accident_zone_score if safety else None,
                "worker_count": _int(safety.worker_count) if safety else 0,
                "violation_count": _int(safety.violation_count) if safety else 0,
                "alert_count": _int(safety.alert_count) if safety else 0,
                "factors": {
                    "ppe": (safety.ppe_factors or []) if safety else [],
                    "worker_safety": (safety.worker_factors or []) if safety else [],
                    "accident_zone": (safety.accident_factors or []) if safety else [],
                },
                "summary": (safety.summary or "") if safety else "",
            },
            "site_risk_summary": {
                "hazards_total": len(hazard_rows),
                "hazards_by_severity": hazards_by_sev,
                "unresolved_hazards": sum(
                    1 for h in hazard_rows if str(h["status"]).lower() != "resolved"
                ),
                "violation_count": len(violation_rows),
                "violations_by_severity": violations_by_sev,
                "open_violation_count": len(open_violations),
                "alert_count": len(alert_rows),
                "alerts_by_severity": alerts_by_sev,
            },
            "compliance_summary": compliance_data,
            "insurance_summary": insurance_data,
            "critical_findings": critical_findings,
            "high_findings": high_findings,
            "open_violations": open_violations,
            "worker_summary": {
                "total": len(worker_rows),
                "present": len(present_workers),
                "ppe_compliant": len(ppe_compliant),
                "ppe_non_compliant": len(ppe_non_compliant),
                "workers": worker_rows,
                "missing_ppe": missing_ppe_entries,
                "violations_by_worker": violations_by_worker,
            },
            "equipment_summary": {
                "total": len(equipment_rows),
                "by_type": equipment_types,
                "active": len(active_equipment),
                "maintenance_issues": len(maintenance_issues),
                "equipment": equipment_rows,
            },
            "ppe_summary": {
                "ppe_compliance": _num(analysis.ppe_compliance),
                "helmet_violations": _int(analysis.helmet_violations),
                "vest_violations": _int(analysis.vest_violations),
                "other_violations": _int(analysis.other_violations),
                "total_violations": _int(analysis.total_violations),
            },
            "recommendations": recs,
            "evidence_summary": evidence_summary,
            "data_quality": data_quality,
            "compliance_findings": finding_rows,
            "insurance_incidents": incident_rows,
            "claim_records": [
                {
                    "id": c.id,
                    "status": c.status,
                    "claim_summary": c.claim_summary,
                }
                for c in claims
            ],
        }


def build_intelligence(db: Session, site_id: str, analysis_id: str) -> dict:
    """Convenience wrapper around the intelligence engine."""
    return IntelligenceEngine().build(db, site_id, analysis_id)


def maybe_notify(db: Session, site_id: str, analysis_id: str) -> list[dict]:
    """Re-run the existing notification workflow against persisted results.

    Uses the exact same ``evaluate_analysis`` contract as the pipeline so chat
    outages / duplicates are governed by the existing dedup + cooldown policy.
    Deliberately failure-safe: any error is logged and swallowed so report
    generation/browse is never blocked by the notification path.
    """
    try:
        ctx = build_intelligence(db, site_id, analysis_id)
        # Fetch persisted rows for the evaluate_analysis contract (same shape
        # the pipeline passes on completion).
        hazards = [
            {"id": h.id, "hazard_type": h.hazard_type, "description": h.description,
             "severity": h.severity, "zone_id": h.zone_id}
            for h in db.query(Hazard).filter(Hazard.analysis_id == analysis_id).all()
        ]
        violations = [
            {"id": v.id, "violation_type": v.violation_type, "description": v.description,
             "severity": v.severity, "worker_id": v.worker_id, "zone_id": v.zone_id}
            for v in db.query(SafetyViolation).filter(SafetyViolation.analysis_id == analysis_id).all()
        ]
        alerts = [
            {"id": a.id, "message": a.message, "severity": a.severity, "zone_id": a.zone_id}
            for a in db.query(SafetyAlert).filter(SafetyAlert.analysis_id == analysis_id).all()
        ]
        incidents = [
            {"id": i.id, "incident_type": i.incident_type, "description": i.description,
             "severity": i.severity, "timestamp": i.timestamp.isoformat() if i.timestamp else None}
            for i in db.query(InsuranceIncident).filter(InsuranceIncident.analysis_id == analysis_id).all()
        ]

        created = evaluate_analysis(
            db,
            site_id,
            analysis_id,
            risk=ctx.get("overall_risk") or {},
            safety=ctx.get("safety_summary") or {},
            alerts=alerts,
            violations=violations,
            hazards=hazards,
            incidents=incidents,
        )
        return [
            {
                "id": n.id,
                "type": n.type,
                "severity": n.severity,
                "title": n.title,
            }
            for n in created
        ]
    except Exception as exc:  # noqa: BLE001 - notification must never break reporting
        logger.warning(
            "maybe_notify failed safely for site=%s analysis=%s: %s",
            site_id, analysis_id, exc,
        )
        return []