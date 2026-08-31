from __future__ import annotations


class SiteConditionAnalyzer:
    """Analyses site-specific conditions and produces a risk score."""

    LIGHTING_SCORES: dict[str, float] = {
        "poor": 20,
        "very_poor": 35,
        "dark": 30,
        "no_lighting": 40,
    }

    GROUND_SCORES: dict[str, float] = {
        "wet": 15,
        "muddy": 25,
        "icy": 40,
        "uneven": 15,
        "unstable": 30,
    }

    COMBINATION_BONUS: list[tuple[list[str], float, str]] = [
        (["wet", "poor"], 10, "Wet ground combined with poor lighting"),
        (["wet", "very_poor"], 15, "Wet ground combined with very poor lighting"),
        (["muddy", "poor"], 15, "Muddy ground combined with poor lighting"),
        (["muddy", "very_poor"], 20, "Muddy ground combined with very poor lighting"),
        (["icy", "poor"], 20, "Icy ground combined with poor lighting"),
        (["icy", "very_poor"], 25, "Icy ground combined with very poor lighting"),
    ]

    def analyze(self, site_conditions: dict, environmental: dict) -> dict:
        score = 0.0
        factors: list[str] = []

        combined_tags: list[str] = []

        score, factors, combined_tags = self._evaluate_lighting(
            site_conditions, environmental, score, factors, combined_tags
        )
        score, factors, combined_tags = self._evaluate_ground(
            site_conditions, environmental, score, factors, combined_tags
        )
        score, factors = self._evaluate_combined(
            combined_tags, score, factors
        )

        score = min(score, 100.0)
        risk_level = self._score_to_level(score)

        return {
            "score": round(score, 2),
            "risk_level": risk_level,
            "factors": factors,
        }

    # ── Private helpers ────────────────────────────────────────────────────

    def _evaluate_lighting(
        self, site_conditions: dict, environmental: dict,
        score: float, factors: list[str], combined_tags: list[str],
    ) -> tuple[float, list[str], list[str]]:
        lighting = str(
            site_conditions.get("lighting", "")
            or environmental.get("lighting", "")
        ).lower().strip()

        if lighting in self.LIGHTING_SCORES:
            contribution = self.LIGHTING_SCORES[lighting]
            score += contribution
            factors.append(f"{lighting.replace('_', ' ').title()} lighting conditions (+{contribution})")
            combined_tags.append(lighting)

        return score, factors, combined_tags

    def _evaluate_ground(
        self, site_conditions: dict, environmental: dict,
        score: float, factors: list[str], combined_tags: list[str],
    ) -> tuple[float, list[str], list[str]]:
        ground = str(
            site_conditions.get("ground_condition", site_conditions.get("ground", ""))
            or environmental.get("ground_condition", environmental.get("ground", ""))
        ).lower().strip()

        if ground in self.GROUND_SCORES:
            contribution = self.GROUND_SCORES[ground]
            score += contribution
            factors.append(f"{ground.title()} ground conditions (+{contribution})")
            combined_tags.append(ground)

        return score, factors, combined_tags

    def _evaluate_combined(
        self, combined_tags: list[str], score: float, factors: list[str]
    ) -> tuple[float, list[str]]:
        tag_set = set(combined_tags)
        for required_tags, bonus, description in self.COMBINATION_BONUS:
            if all(t in tag_set for t in required_tags):
                score += bonus
                factors.append(f"{description} (+{bonus})")
        return score, factors

    def _score_to_level(self, score: float) -> str:
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"
