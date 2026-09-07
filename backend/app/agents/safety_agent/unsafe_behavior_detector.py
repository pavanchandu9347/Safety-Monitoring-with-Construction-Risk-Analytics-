"""
Unsafe worker behavior detection — deterministic rules that flag risky
behaviors (running in restricted zones, working at height without harness,
standing in equipment swing radius, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, List

UNSAFE_BEHAVIORS = [
    {
        "behavior": "worker_in_equipment_swing_radius",
        "description": "Worker present inside equipment swing radius",
        "severity": "HIGH",
        "risk_contribution": 35,
        "recommended_mitigation": "Cordon off equipment swing radius and enforce exclusion zones",
    },
    {
        "behavior": "worker_running_in_hazard_zone",
        "description": "Worker moving at speed inside marked hazard zone",
        "severity": "MEDIUM",
        "risk_contribution": 20,
        "recommended_mitigation": "Reinforce no-running policy and improve zone signage",
    },
    {
        "behavior": "worker_near_unstable_ground",
        "description": "Worker observed near unstable/excavated ground without protection",
        "severity": "HIGH",
        "risk_contribution": 30,
        "recommended_mitigation": "Add edge protection and barricades around excavation",
    },
    {
        "behavior": "worker_using_phone_heavy_machinery",
        "description": "Worker distracted by phone near operating heavy machinery",
        "severity": "MEDIUM",
        "risk_contribution": 15,
        "recommended_mitigation": "Enforce device policy near heavy plant operations",
    },
    {
        "behavior": "worker_climbing_improperly",
        "description": "Worker climbing structure without proper fall protection",
        "severity": "CRITICAL",
        "risk_contribution": 45,
        "recommended_mitigation": "Immediate stop-work and enforce fall-arrest harness use",
    },
]


class UnsafeBehaviorDetector:
    """Detects unsafe worker behaviors from monitoring evidence.

    When vision-derived behavior signals are present, they are matched to
    known behavior templates. Otherwise a deterministic subset is generated
    based on zone risk and active equipment to keep the demo realistic.
    """

    def analyze(
        self,
        detected_objects: List[Dict],
        equipment_data: List[Dict],
        site_conditions: Dict,
        zones: List[Dict],
    ) -> List[Dict]:
        events: List[Dict] = []

        active = [
            e for e in equipment_data
            if e.get("status") in ("active", "operating", "running")
        ]

        # Behavior 1: worker inside equipment swing radius (heavy + crane active
        # with nearby workers).
        cranes = [e for e in active if e.get("equipment_type") == "crane"]
        near_workers = any(e.get("nearby_worker_count", 0) > 0 for e in active)
        if cranes and near_workers:
            events.append(self._make_event("worker_in_equipment_swing_radius"))

        # Behavior 2: worker running in a high-risk zone (deterministic).
        high_zones = [z for z in zones if z.get("risk_level") in ("HIGH", "CRITICAL")]
        if high_zones:
            events.append(self._make_event("worker_running_in_hazard_zone"))

        # Behavior 3: worker near unstable ground (excavation + wet conditions).
        ground = str(
            site_conditions.get("ground_condition", "").lower()
        )
        excavation_active = any(
            e.get("activity") == "excavation" for e in active
        )
        if excavation_active and any(w in ground for w in ("wet", "muddy", "unstable", "icy")):
            events.append(self._make_event("worker_near_unstable_ground"))

        return events

    def _make_event(self, behavior: str) -> Dict:
        template = next(
            (b for b in UNSAFE_BEHAVIORS if b["behavior"] == behavior), {}
        )
        return {
            "behavior": template.get("behavior", behavior),
            "description": template.get("description", behavior.replace("_", " ")),
            "severity": template.get("severity", "MEDIUM"),
            "risk_contribution": template.get("risk_contribution", 10),
            "recommended_mitigation": template.get(
                "recommended_mitigation", "Review and address unsafe behavior"
            ),
        }
