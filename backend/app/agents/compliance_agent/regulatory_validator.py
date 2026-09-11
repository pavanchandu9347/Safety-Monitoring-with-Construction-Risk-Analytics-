"""Regulatory validation — maps each baseline requirement to real evidence.

For every requirement the validator inspects the analysis evidence and returns
a traceable verdict:

* ``COMPLIANT``        — real evidence demonstrates the requirement is met.
* ``NON_COMPLIANT``    — real evidence demonstrates a violation.
* ``NOT_VERIFIED``     — no evidence available; the platform never guesses.

Each verdict carries ``evidence`` text plus an ``evidence_meta`` object
(worker ids, frame numbers, timestamps, source ids) that trace back to the
video analysis — nothing is hardcoded.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from app.agents.compliance_agent.standards_monitor import classify_evidence

REQUIREMENT_CATEGORY = "requirements"

_UNVERIFIED_REASON = "Required documentation/evidence unavailable"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _worker_missing(worker: Dict[str, Any], item: str) -> bool:
    missing = worker.get("missing_ppe") or []
    return item in [str(m).lower() for m in missing]


def _non_compliant_workers(context: Dict[str, Any], ppe_item: str) -> List[Dict[str, Any]]:
    return [
        w for w in (context.get("worker_ppe") or [])
        if w.get("ppe_status") == "non_compliant" and _worker_missing(w, ppe_item)
    ]


def _compliant_workers(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [w for w in (context.get("worker_ppe") or []) if w.get("ppe_status") == "compliant"]


def _assessed_workers(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [w for w in (context.get("worker_ppe") or [])
            if w.get("ppe_status") in ("compliant", "non_compliant")]


def _worker_ids(workers: List[Dict[str, Any]]) -> List[str]:
    return [str(w.get("worker_id") or w.get("name") or "?") for w in workers]


def _unsafe_events(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    safety = context.get("safety") or {}
    events = list(safety.get("unsafe_behavior_events") or [])
    events += [h for h in (context.get("hazards") or [])
               if "equipment" in str(h.get("hazard_type", "")).lower()
               or "proximity" in str(h.get("hazard_type", "")).lower()]
    return events


def _equipment_hazards(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        h for h in (context.get("hazards") or [])
        if "equipment" in str(h.get("hazard_type", "")).lower()
        or "zone" in str(h.get("hazard_type", "")).lower()
    ]


def _lighting(context: Dict[str, Any]) -> str:
    safety = context.get("safety") or {}
    risk = context.get("risk") or {}
    return str(
        safety.get("lighting_condition")
        or (context.get("site_conditions") or {}).get("lighting_condition", "")
        or (context.get("video") or {}).get("lighting_condition", "")
        or ""
    )


def _accident_overall(context: Dict[str, Any]) -> Dict[str, Any]:
    return (context.get("accident_zones") or {}).get("overall_accident_risk", {}) or {}


def _inspection_summary(context: Dict[str, Any]) -> Dict[str, Any]:
    inspections = context.get("inspections") or []
    overdue = sum(1 for i in inspections if i.get("status") == "OVERDUE")
    completed = sum(1 for i in inspections if i.get("status") == "COMPLETED")
    due = sum(1 for i in inspections if i.get("status") == "DUE")
    return {
        "total": len(inspections), "overdue": overdue,
        "completed": completed, "due": due,
    }


def _base_finding(requirement: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "site_id": context.get("site_id"),
        "analysis_id": context.get("analysis_id"),
        "requirement_id": requirement.get("id"),
        "category": requirement.get("category", ""),
        "requirement": requirement.get("requirement", ""),
        "description": requirement.get("description", ""),
        "severity": requirement.get("severity", "MEDIUM"),
        "source": "video_vision",
        "status": "NOT_VERIFIED",
        "evidence": "",
        "evidence_meta": {
            "note": "",
            "analysis_id": context.get("analysis_id"),
            "worker_ids": [],
            "frames": [],
            "timestamps": [],
            "source_ids": [],
        },
        "timestamp": _now_iso(),
    }


def _not_verified(finding: Dict[str, Any], reason: Optional[str] = None) -> Dict[str, Any]:
    finding["status"] = "NOT_VERIFIED"
    finding["source"] = "documentation_required"
    finding["evidence"] = reason or _UNVERIFIED_REASON
    finding["evidence_meta"]["note"] = reason or _UNVERIFIED_REASON
    return finding


def _validate_ppe(finding: Dict[str, Any], context: Dict[str, Any],
                  item: str, label: str, aliases: List[str]) -> Dict[str, Any]:
    req = finding["requirement"].lower()
    if not any(a in req for a in aliases):
        return finding
    bad = _non_compliant_workers(context, item)
    ok = _compliant_workers(context)
    assessed = _assessed_workers(context)

    if bad:
        ids = _worker_ids(bad)
        finding["status"] = "NON_COMPLIANT"
        finding["evidence"] = (
            f"Worker(s) {', '.join(ids)} detected without {label} "
            f"({len(bad)} of {len(assessed)} assessed workers)."
        )
        finding["evidence_meta"]["worker_ids"] = ids
        finding["evidence_meta"]["note"] = "Derived from real PPE detections in video frames."
        finding["evidence_meta"]["source_ids"] = [
            h.get("id") for h in (context.get("violations") or [])
            if "ppe" in str(h.get("violation_type", "")).lower()
        ]
    elif assessed and not bad:
        finding["status"] = "COMPLIANT"
        finding["evidence"] = (
            f"All {len(assessed)} assessed worker(s) detected with {label}."
        )
        finding["evidence_meta"]["worker_ids"] = _worker_ids(assessed)
        finding["evidence_meta"]["note"] = "Derived from real PPE detections in video frames."
    else:
        _not_verified(finding, "No person/PPE evidence in the sampled frames to verify head protection.")
    return finding


def validate_requirement(requirement: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate one requirement against the analysis evidence."""
    finding = _base_finding(requirement, context)
    category = requirement.get("category", "")

    if category == "PPE":
        finding = _validate_ppe(finding, context, "helmet", "head protection", ["helmet", "head"])
        if finding["status"] == "NOT_VERIFIED":
            finding = _validate_ppe(finding, context, "vest", "a high-visibility vest", ["vest", "hi-vis"])
        if finding["status"] == "NOT_VERIFIED":
            finding = _validate_ppe(finding, context, "gloves", "hand protection", ["glove", "hand"])
        if finding["status"] == "NOT_VERIFIED":
            finding = _validate_ppe(finding, context, "boots", "foot protection", ["boot", "foot"])
        return finding

    if category == "Worker Safety":
        events = _unsafe_events(context)
        if events:
            finding["status"] = "NON_COMPLIANT"
            finding["evidence"] = (
                f"{len(events)} unsafe worker–equipment proximity/behaviour event(s) "
                "detected in the video."
            )
            finding["evidence_meta"]["source_ids"] = [e.get("id") for e in events if e.get("id")]
            finding["evidence_meta"]["note"] = "Derived from real unsafe-behaviour detections."
            return finding
        if context.get("worker_ppe") or _assessed_workers(context):
            finding["status"] = "COMPLIANT"
            finding["evidence"] = "No unsafe worker behaviour detected across sampled frames."
            return finding
        return _not_verified(finding)

    if category == "Equipment Safety":
        hazards = _equipment_hazards(context)
        equipment = context.get("equipment") or []
        if hazards:
            finding["status"] = "NON_COMPLIANT"
            finding["evidence"] = (
                f"{len(hazards)} equipment-related hazard(s) detected "
                f"(zone control / proximity)."
            )
            finding["evidence_meta"]["source_ids"] = [h.get("id") for h in hazards if h.get("id")]
            return finding
        if equipment:
            finding["status"] = "COMPLIANT"
            finding["evidence"] = f"{len(equipment)} equipment unit(s) detected without zone violations."
            return finding
        return _not_verified(finding, "No equipment detected in the sampled frames.")

    if category == "Site Safety":
        lighting = _lighting(context)
        if "light" in requirement.get("requirement", "").lower():
            if lighting in ("Good", "Adequate"):
                finding["status"] = "COMPLIANT"
                finding["evidence"] = f"Lighting condition measured from frames: {lighting}."
                return finding
            if lighting in ("Poor", "Dark"):
                finding["status"] = "NON_COMPLIANT"
                finding["evidence"] = f"Lighting condition measured from frames: {lighting}."
                return finding
            return _not_verified(finding, "Lighting could not be measured from the sampled frames.")

        accident = _accident_overall(context)
        if accident.get("evidence_available"):
            level = accident.get("risk_level", "LOW")
            score = accident.get("score", 0)
            if level in ("HIGH", "CRITICAL"):
                finding["status"] = "NON_COMPLIANT"
                finding["evidence"] = f"Top accident-prone zone risk: {level} (score {score})."
            else:
                finding["status"] = "COMPLIANT"
                finding["evidence"] = f"Accident-prone zone risk controlled: {level} (score {score})."
            finding["evidence_meta"]["note"] = "Derived from real spatial detections."
            return finding
        return _not_verified(finding, "No spatial accident-zone evidence available from this analysis.")

    if category == "Inspection":
        summary = _inspection_summary(context)
        if summary["overdue"]:
            finding["status"] = "NON_COMPLIANT"
            finding["evidence"] = (
                f"{summary['overdue']} required inspection(s) are overdue "
                "(no completed inspection record)."
            )
            finding["source"] = "inspection_tracker"
            return finding
        return _not_verified(finding, "Inspection status cannot be verified: no completed inspection records.")

    # Categories that fundamentally require documentation.
    return _not_verified(finding)


def validate_all(requirements: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate every baseline requirement, returning one finding each."""
    findings: List[Dict[str, Any]] = []
    for req in requirements:
        findings.append(validate_requirement(req, context))
    return findings