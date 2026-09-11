"""Compliance scoring.

The overall score is computed from the available verdicts only:

    overall = Σ weight(category)  for categories that are COMPLIANT
            / Σ weight(category)  for categories with a verified verdict
            × 100

Categories with no verdict (NOT_VERIFIED) never count against or for the
score — they are reported separately so the number is honest about how much
of the requirement set is actually evidence-backed.

Category weightings are configurable (``ComplianceAgent(weights=...)``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_WEIGHTS: Dict[str, float] = {
    "PPE": 3.0,
    "Worker Safety": 2.0,
    "Equipment Safety": 2.0,
    "Site Safety": 1.0,
    "Emergency Preparedness": 1.0,
    "Inspection": 1.0,
    "Environmental": 1.0,
    "Documentation": 1.0,
}

STATUSES = ("COMPLIANT", "NON_COMPLIANT")


def compute(
    findings: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Aggregate per-category findings into a weighted compliance score."""
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update({k: float(v) for k, v in weights.items() if v is not None})

    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for f in findings:
        by_cat.setdefault(f.get("category", "Other"), []).append(f)

    category_scores: Dict[str, Any] = {}
    verified_weight_total = 0.0
    compliant_weight_total = 0.0
    requirements_checked = 0
    compliant_count = 0
    non_compliant_count = 0
    not_verified_count = 0

    for category, cat_findings in by_cat.items():
        n_compliant = sum(1 for f in cat_findings if f.get("status") == "COMPLIANT")
        n_non = sum(1 for f in cat_findings if f.get("status") == "NON_COMPLIANT")
        n_nv = sum(1 for f in cat_findings if f.get("status") == "NOT_VERIFIED")

        compliant_count += n_compliant
        non_compliant_count += n_non
        not_verified_count += n_nv

        weight = w.get(category, 1.0)
        verified = n_compliant + n_non
        if verified:
            requirements_checked += verified
            ratio = (n_compliant / verified) * 100
            cat_status = "COMPLIANT" if n_non == 0 else "NON_COMPLIANT"
            if cat_status == "COMPLIANT":
                compliant_weight_total += weight
            verified_weight_total += weight
        else:
            ratio = None
            cat_status = "NOT_VERIFIED"

        category_scores[category] = {
            "category": category,
            "status": cat_status,
            "score": round(ratio, 1) if ratio is not None else None,
            "weight": weight,
            "compliant": n_compliant,
            "non_compliant": n_non,
            "not_verified": n_nv,
            "total": len(cat_findings),
            "verified": verified,
        }

    has_verdict = verified_weight_total > 0
    overall = round((compliant_weight_total / verified_weight_total) * 100, 1) if has_verdict else None

    if overall is None:
        level = "INSUFFICIENT_EVIDENCE"
        score_basis = (
            "No requirements could be verified from available evidence. "
            "The compliance score is NOT shown because none of the applicable "
            "requirements have evidence."
        )
    else:
        level = (
            "NON_COMPLIANT" if overall < 60
            else "COMPLIANT" if overall >= 90
            else "PARTIAL"
        )
        nv_note = (
            f"{not_verified_count} requirement(s) could not be verified and were "
            "excluded from the score."
            if not_verified_count else
            "All applicable requirements were verified."
        )
        score_basis = (
            f"Score computed from {requirements_checked} verified requirement(s)"
            f" across {len([c for c in category_scores.values() if c['verified']])} "
            f"evidence-backed category(ies). {nv_note}"
        )

    return {
        "overall_score": overall,
        "compliance_level": level,
        "score_basis": score_basis,
        "category_scores": category_scores,
        "requirements_checked": requirements_checked,
        "compliant_count": compliant_count,
        "non_compliant_count": non_compliant_count,
        "not_verified_count": not_verified_count,
        "weights": w,
    }