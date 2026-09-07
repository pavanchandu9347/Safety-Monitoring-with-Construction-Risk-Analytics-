"""
Safety hazard detection — translates PPE violations and unsafe behaviors
into structured safety hazards for the safety register.
"""

from __future__ import annotations

from typing import Any, Dict, List

PPE_HAZARD_TMPL = {
    "hazard_type": "ppe_violation",
    "description": "Worker not wearing required personal protective equipment",
    "source": "ppe_detection",
}


class SafetyHazardDetector:
    """Builds safety hazard records from PPE and behavior evidence."""

    def analyze(
        self,
        ppe_assessments: List[Dict],
        unsafe_events: List[Dict],
        detection_source: str = "ppe_detection",
    ) -> List[Dict]:
        hazards: List[Dict] = []

        # Hazards from PPE violations.
        violations = [
            w for w in ppe_assessments if w.get("ppe_status") == "non_compliant"
        ]
        for v in violations:
            missing = ", ".join(m.replace("_", " ") for m in v.get("missing_ppe", []))
            hazards.append(
                {
                    "hazard_type": "ppe_violation",
                    "description": (
                        f"{v.get('worker_id', 'Worker')} missing PPE: {missing or 'unknown'}"
                    ),
                    "severity": "HIGH",
                    "risk_contribution": 35.0,
                    "evidence": (
                        f"{v.get('worker_id')}: missing {missing or 'equipment'} "
                        f"(detected {len(v.get('detected_ppe', []))} of required PPE)"
                    ),
                    "source": detection_source,
                    "recommended_mitigation": (
                        "Issue replacement PPE and enforce mandatory PPE compliance "
                        "at site entrance"
                    ),
                }
            )

        # Hazards from unsafe behaviors.
        for event in unsafe_events:
            hazards.append(
                {
                    "hazard_type": event.get("behavior", "unsafe_behavior"),
                    "description": event.get("description", "Unsafe worker behavior"),
                    "severity": event.get("severity", "MEDIUM"),
                    "risk_contribution": event.get("risk_contribution", 15),
                    "evidence": event.get("description", ""),
                    "source": "worker_behavior",
                    "recommended_mitigation": event.get(
                        "recommended_mitigation",
                        "Review and address unsafe worker behavior",
                    ),
                }
            )

        return hazards
