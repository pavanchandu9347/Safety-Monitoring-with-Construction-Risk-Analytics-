"""
Live risk engine.

Computes an explainable 0-100 site risk score from REAL YOLO detection-derived
statistics, using a short rolling time window so the score reflects recent
observations rather than a single isolated frame.

Scoring contribution model (each scaled 0-100):
  * helmet violations  -> weight 0.35
  * vest violations    -> weight 0.25
  * other/misc PPE     -> weight 0.15
  * violation rate     -> weight 0.25   (share of total workers in violation)

The per-window violation counts are EMA-smoothed (rolling window) so risk rises
when violations persist and gradually falls when they clear, without hiding real
violations behind heavy smoothing.

Risk level mapping uses the project's existing thresholds (see risk_scorer):
  0-24 LOW, 25-49 MEDIUM, 50-74 HIGH, 75-100 CRITICAL.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

# Number of consecutive window observations kept for rolling risk.
ROLLING_WINDOW_SIZE = 30

# EMA smoothing factor applied to per-window violation counts.
EMA_ALPHA = 0.5

# Weight of each violation driver in the final score.
WEIGHTS = {
    "helmet": 0.35,
    "vest": 0.25,
    "other": 0.15,
    "violation_rate": 0.25,
}


class LiveRiskEngine:
    """Rolling, detection-derived risk calculator for a single site."""

    def __init__(self, rolling_window: int = ROLLING_WINDOW_SIZE) -> None:
        self.rolling_window = max(2, rolling_window)
        self._history: List[Dict[str, Any]] = []
        self._ema: Dict[str, float] = {}
        self._reset()

    def _reset(self) -> None:
        self._history.clear()
        self._ema = {
            "workers": 0.0,
            "helmet_violations": 0.0,
            "vest_violations": 0.0,
            "other_violations": 0.0,
            "total_violations": 0.0,
            "violation_rate": 0.0,
        }

    def reset(self) -> None:
        """Clear rolling history (e.g. on start or source change)."""
        self._reset()

    def _push_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self._history.append(snapshot)
        if len(self._history) > self.rolling_window:
            self._history.pop(0)

    def _update_ema(self, key: str, value: float) -> float:
        prev = self._ema.get(key, value)
        updated = EMA_ALPHA * value + (1 - EMA_ALPHA) * prev if self._ema.get(key) is not None else value
        self._ema[key] = updated
        return updated

    def add_observation(
        self,
        *,
        workers: int,
        helmet_violations: int,
        vest_violations: int,
        other_violations: int,
    ) -> Dict[str, Any]:
        """Record one detection-window observation and recompute the live score.

        Args:
            workers: number of active persons detected.
            helmet_violations: workers flagged missing/without helmet.
            vest_violations: workers flagged missing/without vest.
            other_violations: any other PPE violation (gloves/boots/goggles).

        Returns:
            Full live assessment dict (see ``evaluate``).
        """
        workers = max(0, int(workers))
        helmet_violations = max(0, int(helmet_violations))
        vest_violations = max(0, int(vest_violations))
        other_violations = max(0, int(other_violations))

        total_violations = helmet_violations + vest_violations + other_violations
        violation_rate = (total_violations / workers) if workers else 0.0

        # Rolling-window smoothing (EMA over recent observations).
        ema_workers = self._update_ema("workers", workers)
        ema_helmet = self._update_ema("helmet_violations", helmet_violations)
        ema_vest = self._update_ema("vest_violations", vest_violations)
        ema_other = self._update_ema("other_violations", other_violations)
        ema_total = self._update_ema("total_violations", total_violations)
        ema_violation_rate = self._update_ema("violation_rate", violation_rate)

        self._push_snapshot(
            {
                "timestamp": datetime.now(timezone.utc),
                "workers": workers,
                "helmet_violations": helmet_violations,
                "vest_violations": vest_violations,
                "other_violations": other_violations,
                "total_violations": total_violations,
            }
        )

        return self.evaluate(
            workers=ema_workers,
            helmet_violations=ema_helmet,
            vest_violations=ema_vest,
            other_violations=ema_other,
            total_violations=ema_total,
            violation_rate=ema_violation_rate,
        )

    def evaluate(
        self,
        *,
        workers: float,
        helmet_violations: float,
        vest_violations: float,
        other_violations: float,
        total_violations: float,
        violation_rate: float,
    ) -> Dict[str, Any]:
        """Compute the combined live risk assessment (0-100 + level + reasons)."""
        # Each component contributes up to its weight * 100.
        helmet_component = min(helmet_violations, max(1, workers)) / max(1, workers)
        vest_component = min(vest_violations, max(1, workers)) / max(1, workers)
        other_component = min(other_violations, max(1, workers)) / max(1, workers)

        score = round(
            WEIGHTS["helmet"] * 100 * helmet_component
            + WEIGHTS["vest"] * 100 * vest_component
            + WEIGHTS["other"] * 100 * other_component
            + WEIGHTS["violation_rate"] * 100 * violation_rate,
            2,
        )
        score = max(0.0, min(100.0, score))
        level = self._score_to_level(score)
        reasons = self._build_reasons(
            workers=workers,
            helmet_violations=helmet_violations,
            vest_violations=vest_violations,
            other_violations=other_violations,
            total_violations=total_violations,
            violation_rate=violation_rate,
        )

        return {
            "risk_score": score,
            "risk_level": level,
            "workers": int(round(workers)),
            "helmet_violations": int(round(helmet_violations)),
            "vest_violations": int(round(vest_violations)),
            "other_violations": int(round(other_violations)),
            "total_violations": int(round(total_violations)),
            "ppe_compliance": round((1.0 - violation_rate) * 100, 1),
            "reasons": reasons,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 75:
            return "CRITICAL"
        if score >= 50:
            return "HIGH"
        if score >= 25:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _build_reasons(
        *,
        workers: float,
        helmet_violations: float,
        vest_violations: float,
        other_violations: float,
        total_violations: float,
        violation_rate: float,
    ) -> List[str]:
        reasons: List[str] = []
        if helmet_violations > 0:
            reasons.append(
                f"{int(round(helmet_violations))} worker(s) without head protection"
            )
        if vest_violations > 0:
            reasons.append(f"{int(round(vest_violations))} worker(s) without safety vest")
        if other_violations > 0:
            reasons.append(f"{int(round(other_violations))} worker(s) with other PPE violation")
        if workers > 0:
            reasons.append(
                f"PPE compliance at {round((1.0 - violation_rate) * 100)}% "
                f"({int(round(workers))} workers, {int(round(total_violations))} violations)"
            )
        else:
            reasons.append("No workers detected in current field of view")
        if not reasons:
            reasons.append("No active PPE violations detected")
        return reasons


def _now() -> float:
    return time.time()
