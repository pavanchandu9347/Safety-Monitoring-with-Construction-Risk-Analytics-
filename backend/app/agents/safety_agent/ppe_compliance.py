"""
PPE compliance analysis — evaluates PPE violation data and produces a
PPE compliance score with explainable factors.
"""

from __future__ import annotations

from typing import Any, Dict


class PPEDetector:
    """Deterministic PPE compliance analyzer.

    Given a list of per-worker PPE assessments, computes compliance metrics
    and a representative 0-100 compliance score (higher = safer / more
    compliant).
    """

    def analyze(self, worker_ppe: list) -> Dict:
        reported = list(worker_ppe or [])

        total = len(reported)
        compliant = sum(1 for w in reported if w.get("ppe_status") == "compliant")
        non_compliant = total - compliant

        compliance_rate = round(compliant / total, 3) if total else 1.0

        # Score: compliance rate maps inversely to risk.
        score = round((1.0 - compliance_rate) * 100, 2)
        score = min(score, 100.0)

        factors: list = []
        factors.append(f"PPE compliance: {compliant}/{total} workers compliant")
        if total > 0:
            factors.append(f"Compliance rate: {round(compliance_rate * 100)}%")
        missing_counts: dict = {}
        for w in reported:
            for item in w.get("missing_ppe", []):
                missing_counts[item] = missing_counts.get(item, 0) + 1
        for item, cnt in missing_counts.items():
            factors.append(f"{cnt} worker(s) missing {item.replace('_', ' ')}")

        return {
            "score": round(score, 2),
            "risk_level": self._level(score),
            "factors": factors,
            "workers_assessed": total,
            "compliant_count": compliant,
            "non_compliant_count": non_compliant,
            "compliance_rate": compliance_rate,
        }

    @staticmethod
    def _level(score: float) -> str:
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"
