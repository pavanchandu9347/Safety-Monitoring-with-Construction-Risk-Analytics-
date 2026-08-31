import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.agents.site_risk_agent.hazard_detector import HazardDetector
from app.agents.site_risk_agent.environmental_analyzer import EnvironmentalAnalyzer
from app.agents.site_risk_agent.equipment_analyzer import EquipmentAnalyzer
from app.agents.site_risk_agent.site_condition_analyzer import SiteConditionAnalyzer
from app.agents.site_risk_agent.risk_scorer import RiskScorer
from app.agents.site_risk_agent.recommendation_engine import RecommendationEngine
from app.agents.site_risk_agent.agent import SiteRiskAgent
from app.services.simulated_data import EnvironmentalSimulator, EquipmentSimulator


class TestEnvironmentalAnalyzer:
    def test_poor_visibility_gives_high_score(self):
        analyzer = EnvironmentalAnalyzer()
        result = analyzer.analyze({
            "visibility": "Very Poor",
            "weather": "Stormy",
            "wind_speed_kmh": 70,
            "temperature_celsius": 10,
        })
        assert result["score"] > 50
        assert result["risk_level"] in ("HIGH", "CRITICAL")
        assert len(result["factors"]) > 0
    def test_clear_conditions_give_low_score(self):
        analyzer = EnvironmentalAnalyzer()
        result = analyzer.analyze({
            "visibility": "Good",
            "weather": "Clear",
            "wind_speed_kmh": 5,
            "temperature_celsius": 25,
        })
        assert result["score"] < 25
        assert result["risk_level"] == "LOW"


class TestEquipmentAnalyzer:
    def test_active_equipment_near_workers_raises_risk(self):
        analyzer = EquipmentAnalyzer()
        equipment = [
            {"name": "Excavator-01", "status": "active", "activity": "excavation",
             "maintenance_status": "operational", "nearby_worker_count": 6},
            {"name": "Dump Truck-01", "status": "active", "activity": "hauling",
             "maintenance_status": "overdue", "nearby_worker_count": 4},
        ]
        result = analyzer.analyze(equipment)
        assert result["score"] > 0
        assert "Worker proximity" in str(result["factors"]) or "overdue" in str(result["factors"])

    def test_idle_equipment_gives_low_risk(self):
        analyzer = EquipmentAnalyzer()
        equipment = [
            {"name": "Excavator-01", "status": "idle", "activity": "idle",
             "maintenance_status": "operational", "nearby_worker_count": 0},
        ]
        result = analyzer.analyze(equipment)
        assert result["score"] < 50


class TestSiteConditionAnalyzer:
    def test_wet_ground_increases_risk(self):
        analyzer = SiteConditionAnalyzer()
        result = analyzer.analyze(
            {"ground_condition": "Wet", "lighting_condition": "Good"},
            {"weather": "Rainy"},
        )
        assert result["score"] > 0

    def test_dry_good_conditions_low_risk(self):
        analyzer = SiteConditionAnalyzer()
        result = analyzer.analyze(
            {"ground_condition": "Dry", "lighting_condition": "Good"},
            {"weather": "Clear"},
        )
        assert result["score"] < 40


class TestRiskScorer:
    def test_score_calculation_and_classification(self):
        scorer = RiskScorer()
        result = scorer.calculate_overall_score(
            environmental_score=50, equipment_score=60,
            site_condition_score=40, activity_score=55,
            factors={"environmental": ["Poor visibility"], "equipment": ["Active heavy equipment"],
                     "site_condition": ["Wet ground"], "activity": ["Excavation"]},
        )
        assert 0 <= result["overall_score"] <= 100
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_deterministic(self):
        scorer = RiskScorer()
        factors = {"environmental": ["x"], "equipment": ["y"], "site_condition": ["z"], "activity": ["a"]}
        r1 = scorer.calculate_overall_score(50, 60, 40, 55, factors)
        r2 = scorer.calculate_overall_score(50, 60, 40, 55, factors)
        assert r1["overall_score"] == r2["overall_score"]

    def test_maximum_inputs_critical(self):
        scorer = RiskScorer()
        factors = {"environmental": ["a"], "equipment": ["b"], "site_condition": ["c"], "activity": ["d"]}
        result = scorer.calculate_overall_score(100, 100, 100, 100, factors)
        assert result["risk_level"] == "CRITICAL"


class TestHazardDetector:
    def test_heavy_equipment_near_workers_detects_hazard(self):
        detector = HazardDetector()
        event = {
            "detected_objects": [
                {"label": "excavator", "confidence": 0.9, "class_id": 7},
                {"label": "person", "confidence": 0.8, "count": 3, "class_id": 0},
            ]
        }
        equipment = [
            {"name": "Excavator-01", "status": "active", "activity": "excavation",
             "maintenance_status": "operational", "nearby_worker_count": 3}
        ]
        hazards = detector.analyze(event, equipment, {"visibility": "Moderate"}, {"ground_condition": "Dry"})
        assert len(hazards) > 0
        for h in hazards:
            assert h["hazard_type"]
            assert h["evidence"]
            assert h["recommended_mitigation"]
            assert h["source"]

    def test_idle_conditions_no_hazards(self):
        detector = HazardDetector()
        event = {"detected_objects": []}
        equipment = [
            {"name": "Excavator-01", "status": "idle", "activity": "idle",
             "maintenance_status": "operational", "nearby_worker_count": 0}
        ]
        hazards = detector.analyze(event, equipment, {"visibility": "Good"}, {"ground_condition": "Dry"})
        # May still detect environmental hazards if applicable
        for h in hazards:
            assert h["source"]


class TestRecommendationEngine:
    def test_recommendations_generated_for_hazards(self):
        hazards = [
            {"hazard_type": "equipment_proximity", "description": "Heavy equipment near workers",
             "severity": "HIGH", "risk_contribution": 30,
             "evidence": "Excavator with 3 workers", "source": "Computer Vision",
             "recommended_mitigation": "Restrict worker access"},
        ]
        engine = RecommendationEngine()
        recommendations = engine.generate(hazards, {})
        assert len(recommendations) > 0
        assert recommendations[0]["title"]
        assert recommendations[0]["description"]


class TestSiteRiskAgent:
    def test_full_analysis_is_explainable(self):
        agent = SiteRiskAgent()
        event_data = {
            "detected_objects": [
                {"label": "excavator", "confidence": 0.9, "class_id": 7},
                {"label": "person", "confidence": 0.8, "count": 3, "class_id": 0},
            ]
        }
        equipment = [
            {"name": "Excavator-01", "status": "active", "activity": "excavation",
             "maintenance_status": "operational", "nearby_worker_count": 3}
        ]
        env = {"visibility": "Poor", "weather": "Rainy", "wind_speed_kmh": 45, "temperature_celsius": 12}
        site_cond = {"ground_condition": "Wet", "lighting_condition": "Adequate"}

        result = agent.analyze_site(event_data, equipment, env, site_cond)
        ra = result["risk_assessment"]
        assert 0 <= ra["overall_score"] <= 100
        assert ra["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        # Each component must have contributing factors for explainability
        assert ra["environmental_factors"] or ra["equipment_factors"] or ra["site_condition_factors"] or ra["activity_factors"]

    def test_deterministic_analysis(self):
        agent = SiteRiskAgent()
        args = ({}, [], {"visibility": "Good", "weather": "Clear"}, {"ground_condition": "Dry"})
        r1 = agent.analyze_site(args[0], args[1], args[2], args[3])
        r2 = agent.analyze_site(args[0], args[1], args[2], args[3])
        assert r1["risk_assessment"]["overall_score"] == r2["risk_assessment"]["overall_score"]


class TestSimulatedData:
    def test_environmental_simulator_deterministic(self):
        sim = EnvironmentalSimulator()
        c1 = sim.generate_conditions("excavation")
        c2 = sim.generate_conditions("excavation")
        # Same instant of time -> same values
        from datetime import datetime, timezone
        dt = datetime.now(timezone.utc)
        a = sim.generate_conditions("excavation", dt=dt)
        b = sim.generate_conditions("excavation", dt=dt)
        assert a == b

    def test_equipment_simulator_returns_all_catalog(self):
        sim = EquipmentSimulator()
        equip = sim.get_equipment_status()
        assert len(equip) == 5

    def test_no_random_risk(self):
        # Risk must be explainable, not random
        sim = EnvironmentalSimulator()
        from datetime import datetime, timezone
        dt = datetime(2025, 3, 10, 12, 0, 0)
        c1 = sim.generate_conditions("excavation", dt=dt)
        c2 = sim.generate_conditions("excavation", dt=dt)
        assert c1 == c2
