"""Compliance Agent orchestrator (Milestone 3).

Consumes the same evidence set as the Safety/Site-Risk agents (all sharing one
``analysis_id``) and produces an explainable, traceable compliance verdict:

    requirements → regulatory validation → findings
               + policy violations (real safety violations/hazards)
               + inspection tracking
               + weighted compliance score
               + recommendations + report
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.compliance_agent.regulatory_validator import validate_all
from app.agents.compliance_agent.policy_violation_detector import (
    detect as detect_policy_violations,
    open_violation_count,
)
from app.agents.compliance_agent.inspection_tracker import analyze as analyze_inspections
from app.agents.compliance_agent.compliance_scorer import compute as score_compliance
from app.agents.compliance_agent.recommendation_engine import generate as generate_recs
from app.agents.compliance_agent.standards_monitor import monitored_categories


class ComplianceAgent:
    """Main orchestrator for Milestone 3 compliance intelligence."""

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.weights = dict(weights) if weights else None

    def analyze_site(self, context: Dict[str, Any]) -> Dict[str, Any]:
        site_id = context.get("site_id")
        analysis_id = context.get("analysis_id")
        requirements = context.get("requirements") or []
        inspections = context.get("inspections") or []

        # Inspection status is computed first and fed back into the validation
        # context so "Inspection" findings reflect the real tracked status.
        inspection_result = analyze_inspections(inspections)
        validation_context = dict(context)
        validation_context["inspections"] = inspection_result["inspections"]

        findings = validate_all(requirements, validation_context)
        policy_violations = detect_policy_violations(
            context.get("violations") or [],
            context.get("hazards") or [],
            context,
        )
        score_result = score_compliance(findings, weights=self.weights)
        recommendations = generate_recs(
            findings, policy_violations, score_result, inspection_result,
        )
        monitored = monitored_categories(context)

        open_violations = open_violation_count(context.get("violations") or [])
        evidence_available = any(
            f.get("status") in ("COMPLIANT", "NON_COMPLIANT") for f in findings
        )

        verified = [f for f in findings if f.get("status") in ("COMPLIANT", "NON_COMPLIANT")]
        report = {
            "site_id": site_id,
            "analysis_id": analysis_id,
            "assessment_date": datetime.now(timezone.utc).isoformat(),
            "overall_compliance": score_result["overall_score"],
            "compliance_level": score_result["compliance_level"],
            "requirements_checked": score_result["requirements_checked"],
            "compliant_requirements": score_result["compliant_count"],
            "non_compliant_requirements": score_result["non_compliant_count"],
            "not_verified_requirements": score_result["not_verified_count"],
            "open_violations": open_violations,
            "inspection_status": inspection_result,
            "recommendations": recommendations,
            "unavailable_evidence": [
                {
                    "category": c,
                    "status": "NOT_VERIFIED",
                    "reason": "Required documentation/evidence unavailable",
                }
                for c in sorted({f.get("category") for f in findings if f.get("status") == "NOT_VERIFIED"})
            ],
            "evidence": [
                {
                    "category": f.get("category"),
                    "requirement": f.get("requirement"),
                    "status": f.get("status"),
                    "evidence": f.get("evidence"),
                    "evidence_meta": f.get("evidence_meta"),
                }
                for f in verified
            ],
        }

        unavailable = [
            {
                "category": c,
                "status": "NOT_VERIFIED",
                "reason": "Required documentation/evidence unavailable",
            }
            for c in sorted({f.get("category") for f in findings if f.get("status") == "NOT_VERIFIED"})
        ]

        status = (
            "COMPLIANT" if score_result["overall_score"] is not None and score_result["overall_score"] >= 90
            else "NON_COMPLIANT" if score_result["overall_score"] is not None and score_result["overall_score"] < 60
            else "PARTIAL" if score_result["overall_score"] is not None
            else "INSUFFICIENT_EVIDENCE"
        )

        return {
            "status": status,
            "site_id": site_id,
            "analysis_id": analysis_id,
            "overall_score": score_result["overall_score"],
            "compliance_level": score_result["compliance_level"],
            "category_scores": score_result["category_scores"],
            "requirements_checked": score_result["requirements_checked"],
            "compliant_count": score_result["compliant_count"],
            "non_compliant_count": score_result["non_compliant_count"],
            "not_verified_count": score_result["not_verified_count"],
            "open_violations": open_violations,
            "evidence_available": evidence_available,
            "score_basis": score_result["score_basis"],
            "findings": findings,
            "policy_violations": policy_violations,
            "inspections": inspection_result,
            "monitored_categories": monitored,
            "recommendations": recommendations,
            "unavailable_evidence": unavailable,
            "summary": self._summary(status, score_result, findings, open_violations),
            "report": report,
        }

    def _summary(
        self,
        status: str,
        score_result: Dict[str, Any],
        findings: List[Dict[str, Any]],
        open_violations: int,
    ) -> str:
        if status == "INSUFFICIENT_EVIDENCE":
            return (
                "Compliance could not be scored: no requirement in this analysis "
                "carried verifiable evidence. All requirements are reported NOT_VERIFIED."
            )
        nv = score_result["not_verified_count"]
        return (
            f"Compliance is {score_result['compliance_level']} "
            f"({round(score_result['overall_score'], 1)}/100) based on "
            f"{score_result['requirements_checked']} verified requirement(s). "
            f"{nv} requirement(s) could not be verified. "
            f"{open_violations} open safety violation(s) feed the finding set."
        )