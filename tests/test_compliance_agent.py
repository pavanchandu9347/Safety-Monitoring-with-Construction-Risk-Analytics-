"""Unit tests for the Milestone 3 Compliance Agent.

Verifies the no-fabricated-evidence contract: verdicts derive from real
evidence, unverifiable requirements are NOT_VERIFIED, and the score is computed
over verified requirements only.
"""

from app.agents.compliance_agent import ComplianceAgent
from app.services.compliance_baseline import DEFAULT_REQUIREMENTS, _default_inspections


def _rich_context():
    return {
        "site_id": "site_test",
        "analysis_id": "anal_unit_compliance",
        "timestamp": "2026-09-11T10:00:00Z",
        "requirements": DEFAULT_REQUIREMENTS,
        "inspections": _default_inspections(),
        "violations": [
            {"violation_type": "ppe_violation", "severity": "HIGH",
             "description": "Worker W1 missing gloves", "status": "open",
             "source": "ppe_detection"},
        ],
        "hazards": [
            {"hazard_type": "crane_swing", "severity": "HIGH",
             "description": "Crane swing close to workers", "source": "video_vision"},
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
        "alerts": [],
        "accident_zones": {
            "overall_accident_risk": {
                "evidence_available": True, "risk_level": "HIGH", "score": 70,
            }
        },
    }


def test_verdicts_derive_from_evidence():
    result = ComplianceAgent().analyze_site(_rich_context())
    by_category = {}
    for f in result["findings"]:
        by_category.setdefault(f["category"], []).append(f["status"])

    # Real PPE violation drives hand protection NON_COMPLIANT.
    hand = [f for f in result["findings"]
            if "Hand protection" in f.get("requirement", "")][0]
    assert hand["status"] == "NON_COMPLIANT"
    assert "hand protection" in hand["evidence"]

    # Overdue inspection (no record) drives Inspection NON_COMPLIANT.
    insp = [f for f in result["findings"] if f["category"] == "Inspection"][0]
    assert insp["status"] == "NON_COMPLIANT"

    # Accident-prone zone HIGH drives Site Safety NON_COMPLIANT.
    zone = [f for f in result["findings"]
            if "accident-prone" in f.get("requirement", "").lower()][0]
    assert zone["status"] == "NON_COMPLIANT"

    # Documentation-category requirements carry no proof -> NOT_VERIFIED.
    docs = [f for f in result["findings"] if f["category"] == "Documentation"]
    assert docs and all(f["status"] == "NOT_VERIFIED" for f in docs)
    assert docs[0]["evidence"] == "Required documentation/evidence unavailable"


def test_score_uses_verified_only():
    result = ComplianceAgent().analyze_site(_rich_context())
    n_verified = sum(
        1 for f in result["findings"]
        if f["status"] in ("COMPLIANT", "NON_COMPLIANT")
    )
    assert result["requirements_checked"] == n_verified > 0
    assert result["overall_score"] is not None
    assert 0 <= result["overall_score"] <= 100


def test_insufficient_evidence_when_nothing_verified():
    empty = {
        "site_id": "site_test",
        "analysis_id": "anal_unit_empty",
        "requirements": DEFAULT_REQUIREMENTS,
        "inspections": [],  # no inspection reference data available either
        "violations": [],
        "hazards": [],
        "worker_ppe": [],
        "safety": {},
        "alerts": [],
        "accident_zones": {},
    }
    result = ComplianceAgent().analyze_site(empty)
    assert result["overall_score"] is None
    assert result["compliance_level"] == "INSUFFICIENT_EVIDENCE"
    assert all(
        f["status"] == "NOT_VERIFIED"
        for f in result["findings"]
        if f["category"] == "Documentation"
    )


def test_overdue_inspection_is_a_real_verdict():
    result = ComplianceAgent().analyze_site(_rich_context())
    # Reference inspections carry a real due date; no record exists -> OVERDUE.
    statuses = {i["inspection_type"]: i["status"]
                for i in result["inspections"]["inspections"]}
    assert statuses["Daily site walkthrough"] == "OVERDUE"
    insp_finding = [f for f in result["findings"] if f["category"] == "Inspection"][0]
    assert insp_finding["status"] == "NON_COMPLIANT"


def test_recommendations_grounded_in_findings():
    result = ComplianceAgent().analyze_site(_rich_context())
    assert isinstance(result["recommendations"], list)
    assert len(result["recommendations"]) > 0
    for rec in result["recommendations"]:
        assert rec["priority"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert rec["title"]
        assert rec["description"]


def test_report_shape():
    result = ComplianceAgent().analyze_site(_rich_context())
    report = result["report"]
    assert report["site_id"] == "site_test"
    assert report["analysis_id"] == "anal_unit_compliance"
    assert "overall_compliance" in report
    assert "recommendations" in report
    assert "inspection_status" in report
    assert "evidence" in report