"""
Safety Agent orchestrator — consolidates worker safety monitoring, PPE
compliance, unsafe behavior detection, accident-prone zone analysis, and
safety recommendation generation into a single explainable result.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.agents.safety_agent.worker_safety_monitor import WorkerSafetyMonitor
from app.agents.safety_agent.ppe_compliance import PPEDetector as PPEScorer
from app.agents.safety_agent.unsafe_behavior_detector import UnsafeBehaviorDetector
from app.agents.safety_agent.accident_zone_analyzer import AccidentZoneAnalyzer
from app.agents.safety_agent.safety_hazard_detector import SafetyHazardDetector
from app.agents.safety_agent.safety_recommendation_engine import (
    SafetyRecommendationEngine,
)


class SafetyAgent:
    """Main orchestrator for Milestone 2 — worker safety & protection."""

    def __init__(self) -> None:
        self.worker_safety = WorkerSafetyMonitor()
        self.ppe_scorer = PPEScorer()
        self.unsafe_behavior = UnsafeBehaviorDetector()
        self.accident_zones = AccidentZoneAnalyzer()
        self.hazard_detector = SafetyHazardDetector()
        self.recommendation_engine = SafetyRecommendationEngine()

    def analyze_site(
        self,
        worker_ppe: List[Dict],
        equipment_data: List[Dict],
        detected_objects: List[Dict],
        site_conditions: Dict,
        zone_data: List[Dict],
        ppe_source: str = "ppe_detection",
        video_accident_zones: Optional[Dict] = None,
    ) -> Dict:
        # 1. PPE compliance scoring.
        ppe_result = self.ppe_scorer.analyze(worker_ppe)

        # 2. Worker safety monitoring.
        unsafe_events = self.unsafe_behavior.analyze(
            detected_objects, equipment_data, site_conditions, zone_data
        )
        worker_result = self.worker_safety.analyze(
            equipment_data, detected_objects, zone_data, unsafe_events
        )

        # 3. Accident-prone zone analysis. When the video pipeline produced
        # spatial evidence (real detections grouped into frame regions), that is
        # the authoritative source; otherwise fall back to declared zones.
        if video_accident_zones is not None:
            zone_result = video_accident_zones
        else:
            zone_result = self.accident_zones.analyze(zone_data, equipment_data)

        # 4. Safety hazards (PPE violations + unsafe behavior).
        safety_hazards = self.hazard_detector.analyze(
            worker_ppe, unsafe_events, ppe_source
        )

        # 5. Safety recommendations.
        safety_scores = {
            "ppe": ppe_result,
            "safety_monitoring": worker_result,
            "accident_zones": zone_result.get("overall_accident_risk", {}),
        }
        recommendations = self.recommendation_engine.generate(
            safety_hazards, safety_scores, zone_result.get("zones", [])
        )

        # 6. Overall safety score (weighted combination).
        overall = self._combine_overall(
            ppe_result["score"],
            worker_result["score"],
            zone_result.get("overall_accident_risk", {}).get("score", 0),
        )

        summary = (
            f"PPE compliance is {round(ppe_result['compliance_rate']*100)}% "
            f"({ppe_result['compliant_count']} of {ppe_result['workers_assessed']} "
            "workers assessed). "
            f"{len(safety_hazards)} safety hazard(s) identified. "
            f"Highest accident-risk zone: "
            f"{zone_result.get('top_accident_zone', {}).get('zone_name', 'N/A')}."
        )

        evidence_available = bool(
            ppe_result.get("assessed", False)
            or worker_result.get("evidence_available", False)
            or zone_result.get("overall_accident_risk", {}).get("evidence_available", False)
        )

        return {
            "overall_safety_score": overall["score"],
            "overall_safety_level": overall["risk_level"],
            "evidence_available": evidence_available,
            "summary": summary,
            "ppe_compliance": ppe_result,
            "worker_safety": worker_result,
            "accident_zones": zone_result,
            "unsafe_behavior_events": unsafe_events,
            "hazards": safety_hazards,
            "recommendations": recommendations,
        }

    def _combine_overall(self, ppe: float, worker: float, accident: float) -> Dict:
        score = ppe * 0.4 + worker * 0.4 + accident * 0.2
        score = round(min(score, 100.0), 2)
        level = (
            "CRITICAL" if score >= 75
            else "HIGH" if score >= 50
            else "MEDIUM" if score >= 25
            else "LOW"
        )
        return {"score": score, "risk_level": level}
