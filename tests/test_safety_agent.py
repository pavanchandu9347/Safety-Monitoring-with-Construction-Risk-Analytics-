import sys
import os
import pytest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))
sys.path.insert(0, PROJECT_ROOT)

from app.agents.safety_agent.agent import SafetyAgent
from app.agents.safety_agent.worker_safety_monitor import WorkerSafetyMonitor
from app.agents.safety_agent.ppe_compliance import PPEDetector
from app.agents.safety_agent.unsafe_behavior_detector import UnsafeBehaviorDetector
from app.agents.safety_agent.accident_zone_analyzer import AccidentZoneAnalyzer
from app.agents.safety_agent.safety_hazard_detector import SafetyHazardDetector
from app.agents.safety_agent.safety_recommendation_engine import SafetyRecommendationEngine
from app.services.simulated_data import WorkerSafetySimulator


def _base_workers(n=10):
    return [
        {
            "worker_id": f"W-{i}",
            "worker_name": f"Worker {i}",
            "worker_role": "worker",
            "ppe_status": "compliant" if i % 3 else "non_compliant",
            "detected_ppe": ["hardhat", "safety_vest", "gloves"]
            if i % 3 else ["hardhat", "safety_vest"],
            "missing_ppe": [] if i % 3 else ["gloves"],
        }
        for i in range(n)
    ]


class TestPPEDetector:
    def test_compliance_rate(self):
        scorer = PPEDetector()
        result = scorer.analyze(_base_workers(9))
        assert result["workers_assessed"] == 9
        assert result["compliant_count"] == 6
        assert result["compliance_rate"] == pytest.approx(round(6 / 9, 3))

    def test_all_compliant_zero_risk(self):
        scorer = PPEDetector()
        workers = [{
            "worker_id": "W-0", "worker_role": "worker", "ppe_status": "compliant",
            "detected_ppe": ["hardhat"], "missing_ppe": [],
        }]
        result = scorer.analyze(workers)
        assert result["score"] == 0
        assert result["risk_level"] == "LOW"

    def test_deterministic(self):
        scorer = PPEDetector()
        a = scorer.analyze(_base_workers())
        b = scorer.analyze(_base_workers())
        assert a["score"] == b["score"]


class TestWorkerSafetyMonitor:
    def test_unpopulated_low(self):
        monitor = WorkerSafetyMonitor()
        result = monitor.analyze([], [], [], [])
        assert result["worker_count"] == 0

    def test_high_density_raises_score(self):
        monitor = WorkerSafetyMonitor()
        equipment = [
            {"name": "E1", "status": "active", "nearby_worker_count": 6},
            {"name": "E2", "status": "active", "nearby_worker_count": 6},
        ]
        result = monitor.analyze(equipment, [{"class_id": 0}, {"class_id": 0}],
                                 [{"risk_level": "HIGH"}], [{"severity": "HIGH"}])
        assert result["score"] > 0
        assert result["risk_level"] in ("HIGH", "CRITICAL")


class TestUnsafeBehaviorDetector:
    def test_crane_with_workers_flags_swing_radius(self):
        detector = UnsafeBehaviorDetector()
        equipment = [
            {"name": "Crane-01", "equipment_type": "crane", "status": "active",
             "activity": "lifting", "nearby_worker_count": 4},
        ]
        events = detector.analyze([], equipment, {}, [{"risk_level": "HIGH"}])
        assert "worker_in_equipment_swing_radius" in [e["behavior"] for e in events]

    def test_each_event_has_remediation(self):
        detector = UnsafeBehaviorDetector()
        equipment = [
            {"name": "Crane-01", "equipment_type": "crane", "status": "active",
             "activity": "lifting", "nearby_worker_count": 2},
        ]
        events = detector.analyze([], equipment,
                                  {"ground_condition": "Wet"},
                                  [{"risk_level": "HIGH"}])
        assert len(events) >= 2
        for e in events:
            assert e["recommended_mitigation"]


class TestAccidentZoneAnalyzer:
    def test_sorts_by_risk(self):
        analyzer = AccidentZoneAnalyzer()
        zones = [
            {"zone_id": "z1", "zone_name": "A", "risk_level": "LOW", "active_hazard_count": 0},
            {"zone_id": "z2", "zone_name": "B", "risk_level": "CRITICAL", "active_hazard_count": 3},
        ]
        result = analyzer.analyze(zones, [])
        assert result["zones"][0]["zone_name"] == "B"
        assert result["top_accident_zone"]["zone_name"] == "B"


class TestSafetyAgent:
    def test_full_analysis_is_explainable(self):
        agent = SafetyAgent()
        equipment = [
            {"name": "Crane-01", "equipment_type": "crane", "status": "active",
             "activity": "lifting", "zone_id": "z3", "nearby_worker_count": 4},
            {"name": "Excavator-01", "equipment_type": "excavator", "status": "active",
             "activity": "excavation", "zone_id": "z1", "nearby_worker_count": 3},
        ]
        detected = [{"label": "person", "class_id": 0}]
        zones = [
            {"zone_id": "z1", "zone_name": "Excavation A", "risk_level": "HIGH",
             "active_hazard_count": 2},
            {"zone_id": "z3", "zone_name": "Structure C", "risk_level": "MEDIUM",
             "active_hazard_count": 1},
        ]
        result = agent.analyze_site(
            _base_workers(), equipment, detected,
            {"ground_condition": "Wet", "lighting_condition": "Adequate"}, zones,
        )
        assert 0 <= result["overall_safety_score"] <= 100
        assert result["overall_safety_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert result["ppe_compliance"]["workers_assessed"] == 10
        assert result["hazards"]  # some safety hazards present
        assert result["accident_zones"]["zones"]

    def test_deterministic(self):
        agent = SafetyAgent()
        equipment = [{"name": "Crane-01", "equipment_type": "crane", "status": "active",
                      "activity": "lifting", "zone_id": "z3", "nearby_worker_count": 3}]
        zones = [{"zone_id": "z1", "zone_name": "A", "risk_level": "HIGH"}]
        kwargs = dict(
            worker_ppe=_base_workers(), equipment_data=equipment,
            detected_objects=[{"class_id": 0}], site_conditions={}, zone_data=zones,
        )
        r1 = agent.analyze_site(**kwargs)
        r2 = agent.analyze_site(**kwargs)
        assert r1["overall_safety_score"] == r2["overall_safety_score"]


class TestSafetyRecommendationEngine:
    def test_generates_recommendations(self):
        engine = SafetyRecommendationEngine()
        hazards = [
            {"hazard_type": "ppe_violation", "id": "h1", "severity": "HIGH"},
            {"hazard_type": "worker_in_equipment_swing_radius", "id": "h2", "severity": "CRITICAL"},
        ]
        recs = engine.generate(hazards, {"ppe": {"score": 50}, "safety_monitoring": {"score": 30}},
                               [{"zone_name": "A", "accident_risk_level": "HIGH"}])
        assert recs
        assert all(r["title"] for r in recs)


class TestWorkerSimulator:
    def test_deterministic_roster(self):
        sim = WorkerSafetySimulator()
        from datetime import datetime, timezone
        dt = datetime(2025, 5, 1, 8, 0)
        a = sim.get_workers(dt=dt)
        b = sim.get_workers(dt=dt)
        assert a == b
        assert len(a) >= 6

    def test_workers_field_complete(self):
        sim = WorkerSafetySimulator()
        for w in sim.get_workers():
            assert "ppe_status" in w
            assert isinstance(w["missing_ppe"], list)
            assert "detected_ppe" in w


class TestRealPPEDetector:
    """The real PPE detector must never fabricate detections."""

    def test_unavailable_raises_explicit_error(self):
        from ai.computer_vision.ppe_detector import (
            PPEDetector, PPEModelUnavailable,
        )
        det = PPEDetector(model_path="/nonexistent/ppe.pt")
        assert det.available is False
        with pytest.raises(PPEModelUnavailable):
            det.infer(None)

    def test_available_bool_with_missing_model(self):
        from ai.computer_vision.ppe_detector import PPEDetector
        det = PPEDetector(model_path="/nonexistent/ppe.pt")
        assert det.available is False

    def test_image_analysis_reports_unavailable_without_fake_ppe(self):
        """Uploading an image with no PPE model must yield a clear error, not
        fabricated compliance data."""
        import io
        import numpy as np
        from PIL import Image as PILImage, ImageDraw
        from fastapi.testclient import TestClient

        # Draw a synthetic image with a person-like blob.
        pil = PILImage.new("RGB", (320, 320), (60, 70, 80))
        d = ImageDraw.Draw(pil)
        d.rectangle([80, 60, 200, 260], fill=(180, 120, 90))
        buf = io.BytesIO()
        pil.save(buf, format="JPEG")
        buf.seek(0)

        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
        from app.main import app
        import app.api.monitoring as mon
        from app.database.database import get_db

        # Force the detector to a missing model so the honest path is exercised.
        from ai.computer_vision.ppe_detector import PPEDetector

        orig = mon.get_ppe_detector
        mon.get_ppe_detector = lambda: PPEDetector(model_path="/nonexistent/ppe.pt")
        try:
            client = TestClient(app)
            r = client.post(
                "/api/monitoring/process-image",
                files={"file": ("img.jpg", buf.getvalue(), "image/jpeg")},
            )
            assert r.status_code == 200
            body = r.json()
            assert "ppe_compliance" in body
            assert body["ppe_compliance"]["available"] is False
            assert body["ppe_error"] is not None
            # Real base detections still present (not fabricated PPE).
            assert "detections" in body
        finally:
            mon.get_ppe_detector = orig
