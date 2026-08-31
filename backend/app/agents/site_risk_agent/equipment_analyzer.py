from __future__ import annotations


class EquipmentAnalyzer:
    """Analyses equipment-related risk factors."""

    HEAVY_EQUIPMENT_TYPES = frozenset({
        "excavator", "crane", "bulldozer", "backhoe", "loader",
        "forklift", "dump_truck", "concrete_mixer", "paver",
        "telehandler", "pile_driver", "compactor",
    })

    RISK_LEVELS = {
        "LOW": (0, 25),
        "MEDIUM": (25, 50),
        "HIGH": (50, 75),
        "CRITICAL": (75, 100),
    }

    def analyze(
        self, equipment_list: list, detected_objects: list | None = None
    ) -> dict:
        score = 0.0
        factors: list[str] = []

        score, factors = self._evaluate_active_count(equipment_list, score, factors)
        score, factors = self._evaluate_proximity(equipment_list, score, factors)
        score, factors = self._evaluate_maintenance(equipment_list, score, factors)
        score, factors = self._evaluate_zone_density(equipment_list, score, factors)
        score, factors = self._evaluate_heavy_equipment_mix(
            equipment_list, detected_objects, score, factors
        )

        score = min(score, 100.0)
        risk_level = self._score_to_level(score)

        return {
            "score": round(score, 2),
            "risk_level": risk_level,
            "factors": factors,
        }

    # ── Private helpers ────────────────────────────────────────────────────

    def _evaluate_active_count(
        self, equipment_list: list, score: float, factors: list[str]
    ) -> tuple[float, list[str]]:
        active = [e for e in equipment_list if self._is_active(e)]
        count = len(active)
        if count >= 5:
            contribution = 25
            score += contribution
            factors.append(f"{count} active equipment units operating (+{contribution})")
        elif count >= 3:
            contribution = 15
            score += contribution
            factors.append(f"{count} active equipment units operating (+{contribution})")
        return score, factors

    def _evaluate_proximity(
        self, equipment_list: list, score: float, factors: list[str]
    ) -> tuple[float, list[str]]:
        for eq in equipment_list:
            worker_count = self._safe_int(eq.get("nearby_worker_count", 0))
            if worker_count > 0 and self._is_active(eq):
                name = eq.get("name", eq.get("equipment_type", "unknown"))
                contribution = min(10 + worker_count * 5, 30)
                score += contribution
                factors.append(
                    f"'{name}' operating near {worker_count} worker(s) (+{contribution})"
                )
        return score, factors

    def _evaluate_maintenance(
        self, equipment_list: list, score: float, factors: list[str]
    ) -> tuple[float, list[str]]:
        for eq in equipment_list:
            status = str(eq.get("maintenance_status", "")).lower().strip()
            if status in ("overdue", "maintenance_required", "needs_maintenance", "degraded"):
                name = eq.get("name", eq.get("equipment_type", "unknown"))
                contribution = 25
                score += contribution
                factors.append(f"'{name}' has overdue maintenance (+{contribution})")
        return score, factors

    def _evaluate_zone_density(
        self, equipment_list: list, score: float, factors: list[str]
    ) -> tuple[float, list[str]]:
        zone_counts: dict[str, list[str]] = {}
        for eq in equipment_list:
            zone_id = eq.get("zone_id") or "unassigned"
            name = eq.get("name", eq.get("equipment_type", "unknown"))
            zone_counts.setdefault(zone_id, []).append(name)

        for zone_id, names in zone_counts.items():
            if len(names) >= 3:
                contribution = 20
                score += contribution
                zone_label = zone_id if zone_id != "unassigned" else "unassigned zone"
                factors.append(
                    f"{len(names)} heavy equipment in {zone_label} ({', '.join(names)}) (+{contribution})"
                )
        return score, factors

    def _evaluate_heavy_equipment_mix(
        self, equipment_list: list, detected_objects: list | None,
        score: float, factors: list[str],
    ) -> tuple[float, list[str]]:
        has_crane = False
        has_heavy = False
        for eq in equipment_list:
            eq_type = str(eq.get("equipment_type", "")).lower().strip()
            if eq_type == "crane":
                has_crane = True
            if eq_type in self.HEAVY_EQUIPMENT_TYPES:
                has_heavy = True

        if detected_objects is not None:
            for obj in detected_objects:
                obj_type = str(obj.get("type", obj.get("label", ""))).lower().strip()
                if obj_type == "crane":
                    has_crane = True

        if has_crane and has_heavy:
            contribution = 10
            score += contribution
            factors.append(f"Crane operating alongside other heavy equipment (+{contribution})")

        return score, factors

    @staticmethod
    def _is_active(equipment: dict) -> bool:
        status = str(equipment.get("status", "")).lower().strip()
        activity = str(equipment.get("activity", "")).lower().strip()
        return status in ("active", "operating", "running") or activity != ""

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _score_to_level(self, score: float) -> str:
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"
