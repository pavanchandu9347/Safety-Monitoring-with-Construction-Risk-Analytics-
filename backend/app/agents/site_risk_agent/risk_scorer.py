from __future__ import annotations


class RiskScorer:
    """Combines sub-scores into an overall risk assessment."""

    DEFAULT_WEIGHTS = {
        "environmental": 0.25,
        "equipment": 0.30,
        "site_condition": 0.20,
        "activity": 0.25,
    }

    RISK_LEVELS: list[tuple[int, str]] = [
        (75, "CRITICAL"),
        (50, "HIGH"),
        (25, "MEDIUM"),
        (0, "LOW"),
    ]

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = dict(weights or self.DEFAULT_WEIGHTS)
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def calculate_overall_score(
        self,
        environmental_score: float,
        equipment_score: float,
        site_condition_score: float,
        activity_score: float,
        factors: dict[str, list[str]] | None = None,
    ) -> dict:
        factors = factors or {}

        weighted_components = {
            "environmental": environmental_score * self.weights.get("environmental", 0.25),
            "equipment": equipment_score * self.weights.get("equipment", 0.30),
            "site_condition": site_condition_score * self.weights.get("site_condition", 0.20),
            "activity": activity_score * self.weights.get("activity", 0.25),
        }

        overall_score = sum(weighted_components.values())
        overall_score = max(0.0, min(100.0, round(overall_score, 2)))
        risk_level = self._score_to_level(overall_score)

        summary = self._build_summary(
            overall_score,
            risk_level,
            environmental_score,
            equipment_score,
            site_condition_score,
            activity_score,
            weighted_components,
            factors,
        )

        return {
            "overall_score": overall_score,
            "risk_level": risk_level,
            "summary": summary,
        }

    # ── Private helpers ────────────────────────────────────────────────────

    def _score_to_level(self, score: float) -> str:
        for threshold, level in self.RISK_LEVELS:
            if score >= threshold:
                return level
        return "LOW"

    def _build_summary(
        self,
        overall_score: float,
        risk_level: str,
        env_score: float,
        eq_score: float,
        sc_score: float,
        act_score: float,
        weighted: dict[str, float],
        factors: dict[str, list[str]],
    ) -> str:
        parts: list[str] = [
            f"Overall risk level: {risk_level} (score: {overall_score}/100)."
        ]

        parts.append(
            f"Environmental: {env_score}/100 (weight {self.weights.get('environmental', 0.25):.0%}), "
            f"Equipment: {eq_score}/100 (weight {self.weights.get('equipment', 0.30):.0%}), "
            f"Site Conditions: {sc_score}/100 (weight {self.weights.get('site_condition', 0.20):.0%}), "
            f"Activity: {act_score}/100 (weight {self.weights.get('activity', 0.25):.0%})."
        )

        top_contributor = max(weighted, key=weighted.get)
        top_factors = factors.get(top_contributor, [])
        if top_factors:
            parts.append(
                f"Primary risk driver: {top_contributor.replace('_', ' ').title()} "
                f"(top factors: {'; '.join(top_factors[:3])})."
            )

        if risk_level == "CRITICAL":
            parts.append("Immediate intervention required.")
        elif risk_level == "HIGH":
            parts.append("Urgent mitigation measures recommended.")
        elif risk_level == "MEDIUM":
            parts.append("Enhanced monitoring and precautionary measures advised.")
        else:
            parts.append("Site conditions are within acceptable risk parameters.")

        return " ".join(parts)
