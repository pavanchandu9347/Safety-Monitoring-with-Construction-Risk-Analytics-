from __future__ import annotations


class HazardDetector:
    """Detects hazards from monitoring events, equipment, and environmental data."""

    CRANE_TYPES = frozenset({"crane", "tower_crane", "mobile_crane", "crawler_crane"})
    LIFTING_TYPES = frozenset({"crane", "tower_crane", "mobile_crane", "crawler_crane", "hoist"})
    HEAVY_EQUIPMENT_TYPES = frozenset({
        "excavator", "crane", "bulldozer", "backhoe", "loader",
        "forklift", "dump_truck", "concrete_mixer", "paver",
        "telehandler", "pile_driver", "compactor",
    })

    def analyze(
        self,
        monitoring_event: dict,
        equipment_data: list,
        environmental_data: dict,
        site_conditions: dict,
    ) -> list[dict]:
        hazards: list[dict] = []

        detected_objects = monitoring_event.get("detected_objects", [])

        hazards.extend(self._detect_equipment_near_workers(equipment_data, detected_objects))
        hazards.extend(self._detect_poor_visibility_with_equipment(
            environmental_data, equipment_data
        ))
        hazards.extend(self._detect_wet_ground_active_construction(
            site_conditions, environmental_data, equipment_data
        ))
        hazards.extend(self._detect_high_wind_crane(
            environmental_data, equipment_data, detected_objects
        ))
        hazards.extend(self._detect_equipment_proximity(equipment_data, detected_objects))
        hazards.extend(self._detect_env_equipment_combinations(
            environmental_data, equipment_data, detected_objects
        ))

        return hazards

    # ── Detection methods ──────────────────────────────────────────────────

    def _detect_equipment_near_workers(
        self, equipment_data: list, detected_objects: list,
    ) -> list[dict]:
        hazards: list[dict] = []
        worker_objects = [
            o for o in detected_objects
            if self._object_is_worker(o)
        ]

        for eq in equipment_data:
            if not self._is_active(eq):
                continue
            worker_count = self._safe_int(eq.get("nearby_worker_count", 0))
            if worker_count > 0:
                name = eq.get("name", eq.get("equipment_type", "unknown"))
                severity = self._severity_from_count(worker_count)
                hazards.append({
                    "hazard_type": "equipment_proximity",
                    "description": (
                        f"Active equipment '{name}' operating near "
                        f"{worker_count} worker(s)"
                    ),
                    "severity": severity,
                    "risk_contribution": self._proximity_risk(worker_count),
                    "evidence": (
                        f"Equipment '{name}' is {eq.get('status', 'active')} with "
                        f"{worker_count} nearby workers detected"
                    ),
                    "source": "equipment_monitoring",
                    "recommended_mitigation": (
                        f"Enforce exclusion zone around '{name}'. Ensure spotters "
                        f"are assigned when operating near personnel."
                    ),
                })

        if not any(e.get("nearby_worker_count", 0) > 0 for e in equipment_data) and worker_objects:
            worker_count = len(worker_objects)
            severity = self._severity_from_count(worker_count)
            hazards.append({
                "hazard_type": "equipment_proximity",
                "description": (
                    f"{worker_count} worker(s) detected in area with active equipment"
                ),
                "severity": severity,
                "risk_contribution": self._proximity_risk(worker_count),
                "evidence": f"Vision system detected {worker_count} worker(s) in equipment operating zone",
                "source": "vision_detection",
                "recommended_mitigation": "Deploy spotters and enforce exclusion zones.",
            })

        return hazards

    def _detect_poor_visibility_with_equipment(
        self, environmental_data: dict, equipment_data: list,
    ) -> list[dict]:
        hazards: list[dict] = []
        visibility = str(
            environmental_data.get("visibility", "")
        ).lower().strip()

        if visibility not in ("poor", "very_poor", "dark"):
            return hazards

        active_equipment = [e for e in equipment_data if self._is_active(e)]
        if not active_equipment:
            return hazards

        names = [e.get("name", e.get("equipment_type", "unknown")) for e in active_equipment]
        severity = "HIGH" if visibility == "very_poor" else "MEDIUM"

        hazards.append({
            "hazard_type": "poor_visibility",
            "description": (
                f"Poor visibility ({visibility}) with {len(active_equipment)} "
                f"active equipment unit(s): {', '.join(names)}"
            ),
            "severity": severity,
            "risk_contribution": 30 if visibility == "very_poor" else 20,
            "evidence": (
                f"Environmental conditions report visibility: {visibility}; "
                f"active equipment: {', '.join(names)}"
            ),
            "source": "environmental_monitoring",
            "recommended_mitigation": (
                "Reduce equipment operating speed. Deploy additional spotters "
                "and increase site lighting."
            ),
        })

        return hazards

    def _detect_wet_ground_active_construction(
        self, site_conditions: dict, environmental_data: dict, equipment_data: list,
    ) -> list[dict]:
        hazards: list[dict] = []
        ground = str(
            site_conditions.get("ground_condition", site_conditions.get("ground", ""))
            or environmental_data.get("ground_condition", environmental_data.get("ground", ""))
        ).lower().strip()

        if ground not in ("wet", "muddy", "icy", "slippery"):
            return hazards

        active_count = sum(1 for e in equipment_data if self._is_active(e))
        if active_count == 0:
            return hazards

        severity_map = {"icy": "CRITICAL", "muddy": "HIGH", "wet": "MEDIUM", "slippery": "HIGH"}
        severity = severity_map.get(ground, "MEDIUM")

        hazards.append({
            "hazard_type": "wet_ground" if ground != "icy" else "icy_ground",
            "description": (
                f"{ground.title()} ground conditions with {active_count} "
                f"active equipment unit(s) on site"
            ),
            "severity": severity,
            "risk_contribution": {"icy": 35, "muddy": 25, "wet": 15, "slippery": 20}.get(ground, 15),
            "evidence": (
                f"Ground condition: {ground}; active equipment count: {active_count}"
            ),
            "source": "site_conditions",
            "recommended_mitigation": (
                "Apply anti-slip measures. Reduce vehicle speeds. Deploy drainage "
                "if applicable."
            ),
        })

        return hazards

    def _detect_high_wind_crane(
        self, environmental_data: dict, equipment_data: list, detected_objects: list,
    ) -> list[dict]:
        hazards: list[dict] = []
        wind_speed = self._safe_float(
            environmental_data.get("wind_speed", environmental_data.get("wind", 0))
        )

        if wind_speed <= 40:
            return hazards

        has_crane = self._has_crane(equipment_data, detected_objects)
        if not has_crane:
            return hazards

        severity = "CRITICAL" if wind_speed > 60 else "HIGH"

        hazards.append({
            "hazard_type": "crane_high_wind",
            "description": (
                f"High wind ({wind_speed}km/h) with active crane operation"
            ),
            "severity": severity,
            "risk_contribution": 50 if wind_speed > 60 else 35,
            "evidence": f"Wind speed: {wind_speed}km/h; crane detected on site",
            "source": "environmental_monitoring",
            "recommended_mitigation": (
                "Suspend crane operations immediately. Lower loads and secure "
                "boom. Resume only when wind drops below safe threshold."
            ),
        })

        return hazards

    def _detect_equipment_proximity(
        self, equipment_data: list, detected_objects: list,
    ) -> list[dict]:
        hazards: list[dict] = []

        zone_equipment: dict[str, list[dict]] = {}
        for eq in equipment_data:
            if not self._is_active(eq):
                continue
            zone = eq.get("zone_id") or "unassigned"
            zone_equipment.setdefault(zone, []).append(eq)

        for zone_id, eq_list in zone_equipment.items():
            if len(eq_list) >= 3:
                names = [e.get("name", e.get("equipment_type", "unknown")) for e in eq_list]
                zone_label = zone_id if zone_id != "unassigned" else "unassigned zone"

                hazards.append({
                    "hazard_type": "equipment_density",
                    "description": (
                        f"{len(eq_list)} heavy equipment operating in {zone_label}: "
                        f"{', '.join(names)}"
                    ),
                    "severity": "HIGH" if len(eq_list) >= 5 else "MEDIUM",
                    "risk_contribution": min(10 + len(eq_list) * 5, 30),
                    "evidence": (
                        f"Zone {zone_label} contains {len(eq_list)} active equipment units"
                    ),
                    "source": "equipment_monitoring",
                    "recommended_mitigation": (
                        "Redistribute equipment across zones. Implement staggered "
                        "scheduling."
                    ),
                })

        return hazards

    def _detect_env_equipment_combinations(
        self, environmental_data: dict, equipment_data: list, detected_objects: list,
    ) -> list[dict]:
        hazards: list[dict] = []

        weather = str(
            environmental_data.get("weather", environmental_data.get("weather_condition", ""))
        ).lower().strip()
        temperature = self._safe_float(
            environmental_data.get("temperature", environmental_data.get("temp", 20))
        )

        active_count = sum(1 for e in equipment_data if self._is_active(e))
        if active_count == 0:
            return hazards

        if weather in ("stormy", "heavy_rain") and active_count > 0:
            hazards.append({
                "hazard_type": "adverse_weather",
                "description": (
                    f"Adverse weather ({weather}) with {active_count} "
                    f"active equipment on site"
                ),
                "severity": "HIGH",
                "risk_contribution": 30,
                "evidence": f"Weather condition: {weather}; active equipment: {active_count}",
                "source": "environmental_monitoring",
                "recommended_mitigation": (
                    "Activate weather contingency plan. Secure loose materials. "
                    "Consider suspending outdoor operations."
                ),
            })

        if temperature > 35 and active_count > 0:
            hazards.append({
                "hazard_type": "extreme_temperature",
                "description": (
                    f"High temperature ({temperature}°C) with "
                    f"{active_count} active equipment operation"
                ),
                "severity": "MEDIUM",
                "risk_contribution": 20,
                "evidence": f"Temperature: {temperature}°C; active equipment: {active_count}",
                "source": "environmental_monitoring",
                "recommended_mitigation": (
                    "Increase rest breaks. Ensure hydration stations are available. "
                    "Monitor personnel for heat stress."
                ),
            })
        elif temperature < 0 and active_count > 0:
            hazards.append({
                "hazard_type": "extreme_temperature",
                "description": (
                    f"Low temperature ({temperature}°C) with "
                    f"{active_count} active equipment operation"
                ),
                "severity": "MEDIUM",
                "risk_contribution": 25,
                "evidence": f"Temperature: {temperature}°C; active equipment: {active_count}",
                "source": "environmental_monitoring",
                "recommended_mitigation": (
                    "Ensure warming areas are available. Monitor for "
                    "cold-related illness. Verify equipment cold-start procedures."
                ),
            })

        return hazards

    # ── Utility helpers ────────────────────────────────────────────────────

    @staticmethod
    def _is_active(equipment: dict) -> bool:
        status = str(equipment.get("status", "")).lower().strip()
        activity = str(equipment.get("activity", "")).lower().strip()
        return status in ("active", "operating", "running") or activity != ""

    @staticmethod
    def _object_is_worker(obj: dict) -> bool:
        label = str(obj.get("label", obj.get("type", ""))).lower().strip()
        return "person" in label or "worker" in label

    @staticmethod
    def _has_crane(equipment_data: list, detected_objects: list) -> bool:
        for eq in equipment_data:
            eq_type = str(eq.get("equipment_type", "")).lower().strip()
            if eq_type in ("crane", "tower_crane", "mobile_crane", "crawler_crane"):
                return True
        for obj in detected_objects:
            obj_type = str(obj.get("label", obj.get("type", ""))).lower().strip()
            if "crane" in obj_type:
                return True
        return False

    @staticmethod
    def _severity_from_count(worker_count: int) -> str:
        if worker_count >= 5:
            return "CRITICAL"
        if worker_count >= 3:
            return "HIGH"
        if worker_count >= 1:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _proximity_risk(worker_count: int) -> float:
        return min(10.0 + worker_count * 5.0, 40.0)

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
