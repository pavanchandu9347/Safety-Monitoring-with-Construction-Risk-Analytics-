"""Unit tests for the Milestone 3 Insurance Agent.

Verifies incidents are only derived from real HIGH/CRITICAL evidence, claim
documentation only exists when a verified incident exists, and every score is
explainable.
"""

from app.agents.insurance_agent import InsuranceAgent


def _rich_context():
    return {
        "site_id": "site_test",
        "analysis_id": "anal_unit_insurance",
        "timestamp": "2026-09-11T10:00:00Z",
        "requirements": [],
        "inspections": [],
        "violations": [
            {"violation_type": "ppe_violation", "severity": "HIGH",
             "description": "Worker W1 missing gloves", "status": "open"},
        ],
        "hazards": [
            {"hazard_type": "crane_swing", "severity": "HIGH",
             "description": "Crane swing close to workers", "location": "Zone A"},
        ],
        "worker_ppe": [
            {"worker_id": "W1", "ppe_status": "non_compliant", "missing_ppe": ["gloves"]},
            {"worker_id": "W2", "ppe_status": "compliant", "missing_ppe": []},
        ],
        "safety": {
            "overall_safety_score": 55.0,
            "overall_safety_level": "HIGH",
            "ppe_compliance": {
                "compliance_rate": 0.5, "workers_assessed": 2,
                "compliant_count": 1, "non_compliant_count": 1,
            },
            "worker_safety_score": 40.0,
            "unsafe_behavior_events": [{"type": "unsafe_speed"}],
            "hazards": [],
        },
        "alerts": [
            {"alert_type": "fall", "severity": "CRITICAL",
             "message": "Fall detected.", "location": "Zone B"},
        ],
        "accident_zones": {
            "overall_accident_risk": {
                "evidence_available": True, "risk_level": "HIGH", "score": 70,
            }
        },
        "compliance": {"overall_score": 33.3},
    }


def test_incidents_only_from_real_evidence():
    result = InsuranceAgent().analyze_site(_rich_context())
    assert result["incident_count"] == 2  # crane swing + CRITICAL fall alert
    types = sorted(set(i["incident_type"] for i in result["incidents"]))
    assert "Crane Swing" in types
    assert "Fall" in types
    for inc in result["incidents"]:
        assert inc["severity"] in ("HIGH", "CRITICAL")
        assert inc["severity_details"]["severity_level"]


def test_claim_documentation_only_when_incidents_exist():
    result = InsuranceAgent().analyze_site(_rich_context())
    docs = result["claim_documentation"]
    assert docs["status"] == "AVAILABLE"
    assert docs["count"] == result["incident_count"]

    empty = {
        "site_id": "site_test",
        "analysis_id": "anal_unit_insurance_empty",
        "safety": {}, "hazards": [], "alerts": [], "worker_ppe": [],
        "violations": [], "accident_zones": {}, "compliance": {},
    }
    result2 = InsuranceAgent().analyze_site(empty)
    assert result2["incident_count"] == 0
    assert result2["claim_documentation"]["status"] == "NO_CLAIM_DOCUMENTATION"


def test_exposure_from_real_dimensions():
    result = InsuranceAgent().analyze_site(_rich_context())
    exp = result["exposure"]
    # Half the workers non-compliant -> PPE exposure HIGH.
    assert exp["ppe"]["score"] == 50.0
    assert exp["ppe"]["level"] == "HIGH"
    # CRITICAL alerts + HIGH hazard -> incident exposure CRITICAL.
    assert exp["incident"]["score"] == 100.0
    assert exp["incident"]["level"] == "CRITICAL"
    assert all(k in exp for k in ("worker_safety", "equipment", "ppe", "incident"))


def test_claim_risk_explainable():
    result = InsuranceAgent().analyze_site(_rich_context())
    claim = result["claim_risk"]
    assert claim["claim_risk_score"] > 0
    assert claim["contributing_factors"]
    assert all(isinstance(f, str) for f in claim["contributing_factors"])


def test_summary_and_report_shape():
    result = InsuranceAgent().analyze_site(_rich_context())
    report = result["report"]
    assert report["site_id"] == "site_test"
    assert report["analysis_id"] == "anal_unit_insurance"
    assert "insurance_risk_score" in report
    assert "incident_count" in report
    assert result["summary"]
    assert 0 <= result["insurance_risk_score"] <= 100
    assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")