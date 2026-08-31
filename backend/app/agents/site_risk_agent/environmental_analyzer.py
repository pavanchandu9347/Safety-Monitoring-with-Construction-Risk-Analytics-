from __future__ import annotations


class EnvironmentalAnalyzer:
    """Analyses environmental conditions and produces a risk score."""

    RISK_LEVELS = {
        (0, 25): "LOW",
        (25, 50): "MEDIUM",
        (50, 75): "HIGH",
        (50, 75): "HIGH",
        (75, 101): "CRITICAL",
    }

    # Visibility thresholds
    VISIBILITY_SCORES: dict[str, float] = {
        "poor": 30,
        "very_poor": 50,
    }

    # Weather thresholds
    WEATHER_SCORES: dict[str, float] = {
        "rainy": 20,
        "stormy": 40,
        "foggy": 25,
    }

    # Wind thresholds
    WIND_THRESHOLDS: list[tuple[float, float]] = [
        (60, 50),
        (40, 30),
    ]

    # Temperature thresholds: (upper_bound_high_temp, lower_bound_low_temp, contribution)
    # High temp triggers when temperature > upper; Low temp triggers when temperature < lower.
    HIGH_TEMP_THRESHOLD: float = 35.0
    LOW_TEMP_THRESHOLD: float = 0.0
    HIGH_TEMP_SCORE: float = 20.0
    LOW_TEMP_SCORE: float = 25.0

    # Ground condition scores
    GROUND_SCORES: dict[str, float] = {
        "wet": 15,
        "muddy": 25,
        "icy": 40,
    }

    def analyze(self, conditions: dict) -> dict:
        score = 0.0
        factors: list[str] = []

        score, factors = self._evaluate_visibility(conditions, score, factors)
        score, factors = self._evaluate_weather(conditions, score, factors)
        score, factors = self._evaluate_wind(conditions, score, factors)
        score, factors = self._evaluate_temperature(conditions, score, factors)
        score, factors = self._evaluate_ground(conditions, score, factors)

        score = min(score, 100.0)
        risk_level = self._score_to_level(score)

        return {
            "score": round(score, 2),
            "risk_level": risk_level,
            "factors": factors,
        }

    # ── Private helpers ────────────────────────────────────────────────────

    def _evaluate_visibility(
        self, conditions: dict, score: float, factors: list[str]
    ) -> tuple[float, list[str]]:
        visibility = str(conditions.get("visibility", "")).lower().strip().replace(" ", "_")
        if visibility in self.VISIBILITY_SCORES:
            contribution = self.VISIBILITY_SCORES[visibility]
            score += contribution
            factors.append(f"{visibility.replace('_', ' ').title()} visibility (+{contribution})")
        return score, factors

    def _evaluate_weather(
        self, conditions: dict, score: float, factors: list[str]
    ) -> tuple[float, list[str]]:
        weather = str(conditions.get("weather", conditions.get("weather_condition", ""))).lower().strip()
        if weather in self.WEATHER_SCORES:
            contribution = self.WEATHER_SCORES[weather]
            score += contribution
            factors.append(f"{weather.title()} weather (+{contribution})")
        return score, factors

    def _evaluate_wind(
        self, conditions: dict, score: float, factors: list[str]
    ) -> tuple[float, list[str]]:
        wind_speed = self._safe_float(
            conditions.get("wind_speed_kmh", conditions.get("wind_speed", conditions.get("wind", 0)))
        )
        for threshold, contribution in self.WIND_THRESHOLDS:
            if wind_speed > threshold:
                score += contribution
                factors.append(f"Wind speed {wind_speed}km/h exceeds {threshold}km/h (+{contribution})")
                return score, factors
        return score, factors

    def _evaluate_temperature(
        self, conditions: dict, score: float, factors: list[str]
    ) -> tuple[float, list[str]]:
        temperature = self._safe_float(
            conditions.get("temperature_celsius", conditions.get("temperature", conditions.get("temp", 20)))
        )
        if temperature > self.HIGH_TEMP_THRESHOLD:
            score += self.HIGH_TEMP_SCORE
            factors.append(f"High temperature {temperature}°C (>{self.HIGH_TEMP_THRESHOLD}°C) (+{self.HIGH_TEMP_SCORE})")
        elif temperature < self.LOW_TEMP_THRESHOLD:
            score += self.LOW_TEMP_SCORE
            factors.append(f"Low temperature {temperature}°C (<{self.LOW_TEMP_THRESHOLD}°C) (+{self.LOW_TEMP_SCORE})")
        return score, factors

    def _evaluate_ground(
        self, conditions: dict, score: float, factors: list[str]
    ) -> tuple[float, list[str]]:
        ground = str(conditions.get("ground_condition", conditions.get("ground", ""))).lower().strip()
        if ground in self.GROUND_SCORES:
            contribution = self.GROUND_SCORES[ground]
            score += contribution
            factors.append(f"{ground.title()} ground conditions (+{contribution})")
        return score, factors

    def _score_to_level(self, score: float) -> str:
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
