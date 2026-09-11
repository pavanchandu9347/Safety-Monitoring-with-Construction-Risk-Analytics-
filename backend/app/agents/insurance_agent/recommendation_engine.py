"""Insurance recommendations.

Generated strictly from the actual exposure dimensions and claim-risk factors
of the current analysis.
"""

from __future__ import annotations

from typing import Any, Dict, List


def generate(
    exposure: Dict[str, Any],
    claim_risk: Dict[str, Any],
    result: Dict[str, Any],
    compliance: Dict[str, Any],
) -> List[Dict[str, Any]]:
    recommendations: List[Dict[str, Any]] = []
    overall = exposure.get("overall", {})
    risk_level = str(overall.get("level", "LOW")).upper()

    ppe_level = str(exposure["ppe"].get("level", "LOW")).upper()
    if ppe_level in ("HIGH", "CRITICAL"):
        recommendations.append({
            "priority": "HIGH",
            "category": "PPE",
            "recommendation": (
                "High PPE exposure: enforce PPE compliance at site entry and "
                "record daily PPE enforcement logs."
            ),
            "evidence": exposure["ppe"]["factors"][:2],
        })

    incident_level = str(exposure["incident"].get("level", "LOW")).upper()
    if incident_level in ("HIGH", "CRITICAL"):
        recommendations.append({
            "priority": "CRITICAL" if incident_level == "CRITICAL" else "HIGH",
            "category": "Incident Response",
            "recommendation": (
                "Verified incident(s) present: document root cause, capture "
                "witness statements, and file records within 24 hours."
            ),
            "evidence": exposure["incident"]["factors"][:3],
        })

    if risk_level in ("HIGH", "CRITICAL"):
        recommendations.append({
            "priority": "HIGH",
            "category": "Coverage Review",
            "recommendation": (
                "Insurance exposure is HIGH/CRITICAL: review policy adequacy and "
                "premiums for worker injury and equipment coverage."
            ),
            "evidence": ["Overall insurance exposure " + overall.get("level", "LOW") + "."],
        })

    claim_score = float(claim_risk.get("claim_risk_score", 0) or 0)
    if claim_score > 30:
        recommendations.append({
            "priority": "MEDIUM" if claim_score < 60 else "HIGH",
            "category": "Claim Risk",
            "recommendation": (
                "Elevated claim risk: maintain detailed incident documentation and "
                "schedule follow-up safety audits."
            ),
            "evidence": claim_risk.get("contributing_factors", [])[:3],
        })

    if not recommendations:
        recommendations.append({
            "priority": "LOW",
            "category": "Insurance Posture",
            "recommendation": (
                "Maintain current insurance posture; no high-risk exposure "
                "identified in this analysis."
            ),
            "evidence": [],
        })

    return recommendations