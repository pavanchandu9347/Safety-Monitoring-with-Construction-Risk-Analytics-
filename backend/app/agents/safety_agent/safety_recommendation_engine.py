"""
Safety recommendation engine — generates prioritized, actionable safety
recommendations from PPE violations and identified unsafe behaviors.
"""

from __future__ import annotations

from typing import Any, Dict, List

PPE_RECOMMENDATION = {
    "title": "Enforce PPE compliance",
    "description": (
        "Workers are operating without required personal protective equipment. "
        "Re-issue PPE, add gate-level compliance checkpoints, and brief crews "
        "on mandatory PPE rules."
    ),
    "priority": "HIGH",
}

BEHAVIOR_RECOMMENDATIONS: Dict[str, Dict] = {
    "worker_in_equipment_swing_radius": {
        "title": "Restrict equipment swing radius",
        "description": "Cordon off the swing radius of cranes and heavy plant and prohibit worker entry.",
        "priority": "CRITICAL",
    },
    "worker_running_in_hazard_zone": {
        "title": "Reinforce no-running policy",
        "description": "Post signage and supervise movement in marked hazard zones.",
        "priority": "MEDIUM",
    },
    "worker_near_unstable_ground": {
        "title": "Add edge protection",
        "description": "Install barricades and edge protection around excavations and unstable ground.",
        "priority": "HIGH",
    },
    "worker_using_phone_heavy_machinery": {
        "title": "Enforce device policy",
        "description": "Prohibit phone use near operating heavy machinery.",
        "priority": "MEDIUM",
    },
    "worker_climbing_improperly": {
        "title": "Enforce fall protection",
        "description": "Mandate fall-arrest harness use and stop unsafe climbing immediately.",
        "priority": "CRITICAL",
    },
}


class SafetyRecommendationEngine:
    """Generates safety action items from hazards and safety scores."""

    def generate(
        self,
        safety_hazards: List[Dict],
        safety_scores: Dict,
        zone_assessments: List[Dict],
    ) -> List[Dict]:
        recs: List[Dict] = []
        seen: set = set()

        for hazard in safety_hazards:
            htype = hazard.get("hazard_type", "")
            if htype == "ppe_violation" and "ppe_violation" not in seen:
                seen.add("ppe_violation")
                recs.append({
                    **PPE_RECOMMENDATION,
                    "hazard_type": "ppe_violation",
                    "related_hazard_id": hazard.get("id"),
                })
            elif htype in BEHAVIOR_RECOMMENDATIONS and htype not in seen:
                seen.add(htype)
                recs.append({
                    **BEHAVIOR_RECOMMENDATIONS[htype],
                    "hazard_type": htype,
                    "related_hazard_id": hazard.get("id"),
                })

        # Score-driven safety recommendations.
        ppe_score = safety_scores.get("ppe", {}).get("score", 0)
        if ppe_score >= 50:
            recs.append({
                "title": "Escalate PPE safety briefing",
                "description": "PPE non-compliance is high; schedule a mandatory safety briefing.",
                "priority": "HIGH",
                "hazard_type": "ppe_compliance",
            })

        worker_score = safety_scores.get("safety_monitoring", {}).get("score", 0)
        if worker_score >= 60:
            recs.append({
                "title": "Increase supervision on active zones",
                "description": "Elevated unsafe conditions; assign additional safety supervisors.",
                "priority": "MEDIUM",
                "hazard_type": "worker_safety",
            })

        if zone_assessments:
            top = zone_assessments[0]
            if top.get("accident_risk_level") in ("HIGH", "CRITICAL"):
                recs.append({
                    "title": "Prioritize high-accident-risk zone",
                    "description": (
                        f"Zone {top.get('zone_name')} flagged as accident-prone; "
                        "conduct targeted inspection and risk mitigation."
                    ),
                    "priority": "HIGH",
                    "hazard_type": "accident_zone",
                })

        # Sort by severity priority.
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        recs.sort(key=lambda r: order.get(r.get("priority", "LOW"), 9))
        return recs
