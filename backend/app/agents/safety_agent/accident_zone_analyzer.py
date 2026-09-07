"""
Accident-prone zone analysis — identifies zones that are historically or
contextually most likely to produce incidents, and assigns each an
accident risk level plus contributing factors.
"""

from __future__ import annotations

from typing import Any, Dict, List


class AccidentZoneAnalyzer:
    """Evaluates the accident-proneness of each construction zone.

    Combines current risk level, hazard density, and worker/equipment
    activity to produce a per-zone accident risk assessment and an overall
    accident-prone metric.
    """

    def analyze(self, zone_data: List[Dict], equipment_data: List[Dict]) -> Dict:
        zone_assessments: List[Dict] = []
        for zone in zone_data:
            zone_id = zone.get("zone_id") or zone.get("id")
            base_level = (zone.get("risk_level") or "LOW").upper()
            hazard_count = zone.get("active_hazard_count", 0)

            # Equipment density in this zone contributes to accident risk.
            zone_equip = [
                e for e in equipment_data if e.get("zone_id") == zone_id
            ]
            active_zone_equip = [
                e for e in zone_equip
                if e.get("status") in ("active", "operating", "running")
            ]

            base_score = self._level_score(base_level)
            if hazard_count >= 3:
                base_score += 15
            elif hazard_count >= 1:
                base_score += 8
            if len(active_zone_equip) >= 3:
                base_score += 12

            score = min(base_score, 100.0)
            factors = [f"Zone baseline risk: {base_level}"]
            if hazard_count:
                factors.append(f"{hazard_count} active hazards in zone")
            if active_zone_equip:
                factors.append(
                    f"{len(active_zone_equip)} active equipment units in zone"
                )

            zone_assessments.append(
                {
                    "zone_id": zone_id,
                    "zone_name": zone.get("zone_name") or zone.get("name") or zone_id,
                    "accident_risk_score": round(score, 2),
                    "accident_risk_level": self._level(score),
                    "factors": factors,
                    "active_hazard_count": hazard_count,
                    "active_equipment_count": len(active_zone_equip),
                }
            )

        # Sort by descending accident risk.
        zone_assessments.sort(
            key=lambda z: z["accident_risk_score"], reverse=True
        )
        top_zone = zone_assessments[0] if zone_assessments else None

        return {
            "zones": zone_assessments,
            "top_accident_zone": top_zone,
            "overall_accident_risk": self._overall(zone_assessments),
        }

    @staticmethod
    def _level_score(level: str) -> float:
        return {
            "LOW": 10, "MEDIUM": 30, "HIGH": 55, "CRITICAL": 80,
        }.get(str(level).upper(), 10)

    @staticmethod
    def _level(score: float) -> str:
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"

    @staticmethod
    def _overall(zone_assessments: List[Dict]) -> Dict:
        if not zone_assessments:
            return {"score": 0.0, "risk_level": "LOW", "factors": []}
        # Weighted toward the highest-risk zone.
        top = zone_assessments[0]
        second = zone_assessments[1] if len(zone_assessments) > 1 else None
        score = top["accident_risk_score"] * 0.7
        if second:
            score += second["accident_risk_score"] * 0.3
        score = min(score, 100.0)
        return {
            "score": round(score, 2),
            "risk_level": AccidentZoneAnalyzer._level(score),
            "factors": [
                f"Highest-risk zone: {top['zone_name']} "
                f"({top['accident_risk_level']})"
            ],
        }
