"""Explainable insurance risk score.

    Insurance Risk = Σ weight(dimension) × exposure(dimension)
                     + claim-risk uplift

The score is fully deterministic from the analysis evidence and changes when
the underlying safety/incident evidence changes. Weights are configurable.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

DEFAULT_WEIGHTS: Dict[str, float] = {
    "worker_safety": 0.30,
    "equipment": 0.20,
    "ppe": 0.30,
    "incident": 0.20,
}


def _level(score: float) -> str:
    if score < 25:
        return "LOW"
    if score < 50:
        return "MEDIUM"
    if score < 75:
        return "HIGH"
    return "CRITICAL"


def compute(
    exposure: Dict[str, Any],
    claim_risk: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update({k: float(v) for k, v in weights.items() if v is not None})

    base = (
        exposure["worker_safety"]["score"] * w["worker_safety"]
        + exposure["equipment"]["score"] * w["equipment"]
        + exposure["ppe"]["score"] * w["ppe"]
        + exposure["incident"]["score"] * w["incident"]
    )
    uplift = float(claim_risk.get("claim_risk_score", 0) or 0) * 0.15
    score = round(min(base + uplift, 100.0), 1)

    factors: list = []
    for name, meta in exposure.items():
        if name in ("overall", "evidence_available"):
            continue
        if meta["score"] >= 50:
            factors.append(
                f"{name.replace('_', ' ').title()} exposure {meta['level']} ({meta['score']})."
            )
    for f in claim_risk.get("contributing_factors", []):
        factors.append(f)

    return {
        "insurance_risk_score": score,
        "risk_level": _level(score),
        "factors": factors,
        "weights": w,
    }