"""Deterministic safety-alert generation from REAL analysis results.

Alerts are pure rule-based transforms of the evidence the video analysis
produced (PPE violations, compliance rate, safety level). No random or simulated
inputs are used anywhere in this module.
"""

from __future__ import annotations

from typing import Any, Dict, List


def build_safety_alerts(
    violations: List[Dict[str, Any]],
    ppe_compliance_rate: float,
    overall_safety_level: str,
) -> List[Dict[str, Any]]:
    """Build operator alerts strictly from the supplied real violation list.

    Args:
        violations: Real recorded violations (``status``, ``severity``).
        ppe_compliance_rate: Real PPE compliance rate (0-1).
        overall_safety_level: Real overall safety level (LOW..CRITICAL).

    Returns:
        List of ``{alert_type, message, severity}`` dicts.
    """
    alerts: List[Dict[str, Any]] = []

    open_violations = [v for v in violations if v.get("status") == "open"]
    critical = [v for v in open_violations if v.get("severity") == "CRITICAL"]
    high = [v for v in open_violations if v.get("severity") == "HIGH"]

    if critical:
        alerts.append({
            "alert_type": "critical_ppe_violation",
            "message": (
                f"CRITICAL: {len(critical)} open violation(s) on video analysis "
                "— immediate supervisor intervention required."
            ),
            "severity": "CRITICAL",
        })
    elif high:
        alerts.append({
            "alert_type": "high_ppe_violation",
            "message": (
                f"Warning: {len(high)} high-severity open violation(s) recorded. "
                "Review safety compliance in affected zones."
            ),
            "severity": "HIGH",
        })

    if ppe_compliance_rate < 0.8:
        alerts.append({
            "alert_type": "low_compliance",
            "message": (
                f"Site-wide PPE compliance below 80% "
                f"({round(ppe_compliance_rate * 100)}%) on video analysis. "
                "Schedule safety briefing."
            ),
            "severity": "MEDIUM",
        })

    if overall_safety_level in ("HIGH", "CRITICAL"):
        alerts.append({
            "alert_type": "elevated_safety_risk",
            "message": (
                f"Overall safety level {overall_safety_level} from video "
                "analysis. Activate enhanced worker protection protocols."
            ),
            "severity": overall_safety_level,
        })

    if len(open_violations) >= 3:
        alerts.append({
            "alert_type": "multiple_violations",
            "message": (
                f"{len(open_violations)} open violation(s) flagged in this "
                "analysis. Conduct a job-site safety review."
            ),
            "severity": "MEDIUM",
        })

    return alerts