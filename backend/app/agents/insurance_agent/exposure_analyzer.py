"""Insurance exposure analysis.

Exposure is computed strictly from real analysis evidence. Each dimension is
scored 0-100 (higher = worse) and mapped to LOW/MEDIUM/HIGH/CRITICAL.
"""

from __future__ import annotations

from typing import Any, Dict


def _level(score: float) -> str:
    if score < 25:
        return "LOW"
    if score < 50:
        return "MEDIUM"
    if score < 75:
        return "HIGH"
    return "CRITICAL"


def _severity_weight(severity: str) -> float:
    return {"LOW": 15, "MEDIUM": 30, "HIGH": 55, "CRITICAL": 80}.get(
        str(severity).upper(), 25
    )


def analyze(context: Dict[str, Any]) -> Dict[str, Any]:
    safety = context.get("safety") or {}
    compliance = context.get("compliance") or {}
    worker_ppe = context.get("worker_ppe") or []
    hazards = context.get("hazards") or []
    incidents = context.get("incidents") or []

    # ── PPE exposure ────────────────────────────────────────────────────────
    ppe = safety.get("ppe_compliance") or {}
    compliance_rate = ppe.get("compliance_rate", 1.0)
    assessed = ppe.get("workers_assessed", len(worker_ppe))
    ppe_exposure_score = round((1.0 - float(compliance_rate or 1.0)) * 100, 1) if assessed else 0.0
    ppe_factors: list = []
    if ppe_exposure_score > 0:
        ppe_factors.append(f"PPE compliance at {round(float(compliance_rate) * 100)}% "
                           f"({ppe.get('non_compliant_count', 0)} non-compliant worker(s)).")
    if not assessed:
        ppe_factors.append("No PPE evidence available in this analysis.")

    # ── Worker safety exposure ─────────────────────────────────────────────
    worker_score = float(safety.get("worker_safety_score", 0) or 0)
    unsafe_events = safety.get("unsafe_behavior_events") or []
    density_hazards = [
        h for h in hazards
        if any(k in str(h.get("hazard_type", "")).lower() for k in ("proximity", "density", "swing"))
    ]
    worker_exposure_score = round(min((100 - worker_score) * 0.6 + len(density_hazards) * 12, 100), 1)
    worker_factors: list = []
    if density_hazards:
        worker_factors.append(f"{len(density_hazards)} worker–equipment proximity hazard(s).")
    if unsafe_events:
        worker_factors.append(f"{len(unsafe_events)} unsafe behaviour event(s) observed.")
    if not worker_factors:
        worker_factors.append("No worker-safety exposure evidence in this analysis.")

    # ── Equipment exposure ─────────────────────────────────────────────────
    equipment_hazards = [
        h for h in hazards
        if "equipment" in str(h.get("hazard_type", "")).lower()
        or "zone" in str(h.get("hazard_type", "")).lower()
    ]
    equipment_exposure_score = round(
        min(sum(_severity_weight(h.get("severity")) for h in equipment_hazards), 100), 1
    ) if equipment_hazards else 0.0
    equipment_factors: list = []
    if equipment_hazards:
        equipment_factors.append(
            f"{len(equipment_hazards)} equipment/zone hazard(s) detected "
            f"({sum(h.get('severity') in ('HIGH', 'CRITICAL') for h in equipment_hazards)} severe)."
        )
    if not equipment_hazards:
        equipment_factors.append("No equipment hazards detected in this analysis.")

    # ── Incident exposure ──────────────────────────────────────────────────
    incident_exposure_score = 0.0
    incident_factors: list = []
    for inc in incidents:
        sev = str(inc.get("severity", "LOW")).upper()
        incident_exposure_score += _severity_weight(sev)
        incident_factors.append(
            f"{inc.get('incident_type', 'incident')} ({sev}) — {inc.get('description', '')}"
        )
    incident_exposure_score = round(min(incident_exposure_score, 100), 1)
    if not incidents:
        incident_factors.append("No verified incidents in this analysis.")

    # ── Overall exposure ───────────────────────────────────────────────────
    overall_score = round(
        worker_exposure_score * 0.30
        + equipment_exposure_score * 0.25
        + ppe_exposure_score * 0.30
        + incident_exposure_score * 0.15,
        1,
    )

    return {
        "overall": {"score": overall_score, "level": _level(overall_score)},
        "worker_safety": {"score": worker_exposure_score, "level": _level(worker_exposure_score),
                          "factors": worker_factors},
        "equipment": {"score": equipment_exposure_score, "level": _level(equipment_exposure_score),
                      "factors": equipment_factors},
        "ppe": {"score": ppe_exposure_score, "level": _level(ppe_exposure_score),
                "factors": ppe_factors},
        "incident": {"score": incident_exposure_score, "level": _level(incident_exposure_score),
                     "factors": incident_factors},
        "evidence_available": bool(
            worker_exposure_score or equipment_exposure_score or ppe_exposure_score or incident_exposure_score
        ),
    }