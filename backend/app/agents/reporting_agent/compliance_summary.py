"""Compliance summary section for the Reporting Agent (Milestone 4).

Honors the project rule: NOT_VERIFIED never becomes NON_COMPLIANT. Percentages
are computed only from real checked requirements with real status.
"""

from __future__ import annotations

from typing import Any, Optional


def _pct(part: float, whole: float) -> Optional[float]:
    if not whole:
        return None
    return round((part / whole) * 100, 1)


def build(ctx: dict) -> dict:
    data = ctx.get("compliance_summary")
    if data is None:
        return {
            "status": "NOT_AVAILABLE",
            "summary": (
                "Compliance intelligence unavailable for this analysis "
                "(no persisted compliance assessment found)."
            ),
        }

    level = data.get("compliance_level") or "INSUFFICIENT_EVIDENCE"
    checked = int(data.get("requirements_checked") or 0)
    compliant = int(data.get("compliant_count") or 0)
    non_compliant = int(data.get("non_compliant_count") or 0)
    not_verified = int(data.get("not_verified_count") or 0)

    basis = []
    if checked:
        basis.append(f"{checked} requirement(s) checked")
        if compliant:
            basis.append(f"{compliant} compliant")
        if non_compliant:
            basis.append(f"{non_compliant} non-compliant")
        if not_verified:
            basis.append(f"{not_verified} not verified (no evidence either way)")

    summary_text = (data.get("summary") or "").strip()
    return {
        "status": "AVAILABLE",
        "compliance_level": level,
        "overall_score": data.get("overall_score"),
        "requirements_checked": checked,
        "compliant_count": compliant,
        "non_compliant_count": non_compliant,
        "not_verified_count": not_verified,
        "open_violations": data.get("open_violations"),
        "overdue_inspections": data.get("overdue_inspections"),
        "evidence_available": data.get("evidence_available"),
        "score_basis": (data.get("score_basis") or "") if summary_text == "" else summary_text,
        "category_scores": data.get("category_scores", {}),
        "summary": " ".join(basis) or "No requirements have evidence in this analysis.",
    }