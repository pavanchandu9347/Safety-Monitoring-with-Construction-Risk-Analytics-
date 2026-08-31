from __future__ import annotations

from app.agents.site_risk_agent.hazard_detector import HazardDetector
from app.agents.site_risk_agent.environmental_analyzer import EnvironmentalAnalyzer
from app.agents.site_risk_agent.equipment_analyzer import EquipmentAnalyzer
from app.agents.site_risk_agent.site_condition_analyzer import SiteConditionAnalyzer
from app.agents.site_risk_agent.risk_scorer import RiskScorer
from app.agents.site_risk_agent.recommendation_engine import RecommendationEngine


class SiteRiskAgent:
    """Main orchestrator that runs all sub-analyzers and produces a unified result."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.hazard_detector = HazardDetector()
        self.environmental_analyzer = EnvironmentalAnalyzer()
        self.equipment_analyzer = EquipmentAnalyzer()
        self.site_condition_analyzer = SiteConditionAnalyzer()
        self.risk_scorer = RiskScorer(weights=weights)
        self.recommendation_engine = RecommendationEngine()

    def analyze_site(
        self,
        event_data: dict,
        equipment_data: list,
        environmental_data: dict,
        site_conditions: dict,
        detected_objects: list | None = None,
    ) -> dict:
        if detected_objects is None:
            detected_objects = event_data.get("detected_objects", [])

        monitoring_event = dict(event_data)
        monitoring_event["detected_objects"] = detected_objects

        hazards = self.hazard_detector.analyze(
            monitoring_event, equipment_data, environmental_data, site_conditions,
        )

        env_result = self.environmental_analyzer.analyze(environmental_data)

        eq_result = self.equipment_analyzer.analyze(equipment_data, detected_objects)

        sc_result = self.site_condition_analyzer.analyze(site_conditions, environmental_data)

        activity_factors = self._derive_activity_factors(hazards)
        activity_score = self._activity_score_from_hazards(hazards)

        risk_assessment = self.risk_scorer.calculate_overall_score(
            environmental_score=env_result["score"],
            equipment_score=eq_result["score"],
            site_condition_score=sc_result["score"],
            activity_score=activity_score,
            factors={
                "environmental": env_result["factors"],
                "equipment": eq_result["factors"],
                "site_condition": sc_result["factors"],
                "activity": activity_factors,
            },
        )

        risk_scores = {
            "environmental": env_result,
            "equipment": eq_result,
            "site_condition": sc_result,
            "activity": {
                "score": activity_score,
                "risk_level": self._score_to_level(activity_score),
                "factors": activity_factors,
            },
            "overall": risk_assessment,
        }

        recommendations = self.recommendation_engine.generate(hazards, risk_scores)

        return {
            "hazards": hazards,
            "risk_assessment": {
                "overall_score": risk_assessment["overall_score"],
                "risk_level": risk_assessment["risk_level"],
                "environmental_score": env_result["score"],
                "environmental_risk_level": env_result["risk_level"],
                "environmental_factors": env_result["factors"],
                "equipment_score": eq_result["score"],
                "equipment_risk_level": eq_result["risk_level"],
                "equipment_factors": eq_result["factors"],
                "site_condition_score": sc_result["score"],
                "site_condition_risk_level": sc_result["risk_level"],
                "site_condition_factors": sc_result["factors"],
                "activity_score": activity_score,
                "activity_risk_level": self._score_to_level(activity_score),
                "activity_factors": activity_factors,
                "summary": risk_assessment["summary"],
            },
            "recommendations": recommendations,
        }

    # ── Private helpers ────────────────────────────────────────────────────

    def _derive_activity_factors(self, hazards: list[dict]) -> list[str]:
        factors: list[str] = []
        for hazard in hazards:
            severity = hazard.get("severity", "LOW").upper()
            hazard_type = hazard.get("hazard_type", "unknown")
            contribution = hazard.get("risk_contribution", 0)
            factors.append(
                f"{hazard_type.replace('_', ' ').title()} "
                f"(severity: {severity}, contribution: +{contribution})"
            )
        return factors

    def _activity_score_from_hazards(self, hazards: list[dict]) -> float:
        if not hazards:
            return 0.0
        total = sum(h.get("risk_contribution", 0) for h in hazards)
        return min(total, 100.0)

    def _score_to_level(self, score: float) -> str:
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"
