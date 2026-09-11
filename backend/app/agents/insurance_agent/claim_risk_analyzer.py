"""Claim-risk analysis.

Evaluates whether the existing evidence indicates elevated insurance claim
risk. Every contributing factor listed is real: it only appears if the
corresponding evidence actually exists.
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


def analyze(
    context: Dict[str, Any],
    incidents: list,
    compliance: Dict[str, Any],
) -> Dict[str, Any]:
    safety = context.get("safety") or {}
    ppe = safety.get("ppe_compliance") or {}
    hazards = context.get("hazards") or []

    contributing_factors: list = []
    score = 0.0
    evidence: list = []

    # PPE non-compliance.
    non_compliant = int(ppe.get("non_compliant_count", 0) or 0)
    compliance_rate = float(ppe.get("compliance_rate", 1.0) or 1.0)
    if non_compliant > 0:
        weight = min(non_compliant * 12 + (1 - compliance_rate) * 30, 45)
        contributing_factors.append(
            f"{non_compliant} PPE violation(s) "
            f"(compliance {round(compliance_rate * 100)}%)."
        )
        score += weight
        evidence.append({"kind": "ppe_violations", "count": non_compliant})

    # High-severity hazards.
    severe = [h for h in hazards if str(h.get("severity", "")).upper() in ("HIGH", "CRITICAL")]
    if severe:
        severe_types = list(dict.fromkeys(str(h.get("hazard_type", "hazard")) for h in severe))
        contributing_factors.append(
            f"{len(severe)} high-severity hazard(s) detected "
            f"({', '.join(severe_types[:3])})."
        )
        score += min(len(severe) * 15, 40)
        evidence.append({"kind": "high_severity_hazards", "count": len(severe),
                         "ids": [h.get("id") for h in severe if h.get("id")]})

    # Verified incidents.
    if incidents:
        contributing_factors.append(
            f"{len(incidents)} verified incident(s) "
            f"(peak severity {max((str(i.get('severity', 'LOW')).upper() for i in incidents), default='LOW')})."
        )
        score += min(len(incidents) * 12, 35)
        evidence.append({"kind": "incidents", "count": len(incidents)})

    # Repeated violations.
    violations = context.get("violations") or []
    if len(violations) > 1:
        contributing_factors.append(f"{len(violations)} recorded safety violation(s) (repeated exposure).")
        score += min(len(violations) * 3, 15)

    # Accident-prone zone presence.
    zones = (context.get("accident_zones") or {})
    overall = (zones.get("overall_accident_risk") or {})
    if overall.get("evidence_available") and str(overall.get("risk_level", "LOW")).upper() in ("HIGH", "CRITICAL"):
        contributing_factors.append(
            f"Accident-prone zone risk: {overall.get('risk_level')} "
            f"(score {overall.get('score')})."
        )
        score += 15
        evidence.append({"kind": "accident_zones", "level": overall.get("risk_level")})

    if len(contributing_factors) < 2 and compliance.get("overall_score") is None:
        contributing_factors.append(
            "Insufficient evidence to identify claim-risk factors."
        )

    claim_score = round(min(score, 100.0), 1)
    return {
        "claim_risk_score": claim_score,
        "claim_risk_level": _level(claim_score),
        "contributing_factors": contributing_factors,
        "evidence": evidence,
    }