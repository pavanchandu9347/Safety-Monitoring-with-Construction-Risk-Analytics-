"""Simulated environmental and equipment data services for demo purposes.

All data is deterministic based on time seeds and predefined scenarios.
No random values without identifiable factors.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


def _seed_from_time(seed: str, dt: datetime | None = None) -> int:
    """Derive a deterministic integer seed from a string and optional datetime."""
    dt = dt or datetime.now(timezone.utc)
    payload = f"{seed}:{dt.year}:{dt.month}:{dt.day}:{dt.hour}:{dt.minute}"
    return int(hashlib.md5(payload.encode()).hexdigest()[:8], 16)


def _pick(options: list[Any], seed: int) -> Any:
    """Deterministically pick an item from a list using a seed."""
    return options[seed % len(options)]


# ---------------------------------------------------------------------------
# Environmental Simulator
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "clear_day": {
        "weather": "Clear",
        "visibility": "Good",
        "ground_condition": "Dry",
        "lighting_condition": "Good",
        "temp_range": (22, 35),
        "humidity_range": (20, 45),
        "wind_range": (0, 20),
    },
    "rainy": {
        "weather": "Rainy",
        "visibility": "Moderate",
        "ground_condition": "Wet",
        "lighting_condition": "Adequate",
        "temp_range": (8, 22),
        "humidity_range": (70, 100),
        "wind_range": (10, 40),
    },
    "stormy": {
        "weather": "Stormy",
        "visibility": "Poor",
        "ground_condition": "Muddy",
        "lighting_condition": "Poor",
        "temp_range": (5, 15),
        "humidity_range": (80, 100),
        "wind_range": (40, 80),
    },
    "hot_afternoon": {
        "weather": "Clear",
        "visibility": "Good",
        "ground_condition": "Dry",
        "lighting_condition": "Good",
        "temp_range": (35, 40),
        "humidity_range": (20, 40),
        "wind_range": (0, 15),
    },
    "foggy_morning": {
        "weather": "Foggy",
        "visibility": "Very Poor",
        "ground_condition": "Damp",
        "lighting_condition": "Poor",
        "temp_range": (5, 12),
        "humidity_range": (85, 100),
        "wind_range": (0, 10),
    },
    "overcast": {
        "weather": "Cloudy",
        "visibility": "Moderate",
        "ground_condition": "Damp",
        "lighting_condition": "Adequate",
        "temp_range": (12, 25),
        "humidity_range": (50, 75),
        "wind_range": (5, 25),
    },
}

SCENARIO_NAMES = list(SCENARIOS.keys())

ZONE_MODIFIERS: dict[str, dict[str, Any]] = {
    "excavation": {
        "ground_condition_offset": ["Muddy", "Wet"],
        "visibility_offset": ["Moderate"],
    },
    "material_storage": {
        "ground_condition_offset": ["Dry"],
        "visibility_offset": [],
    },
    "building_structure": {
        "ground_condition_offset": [],
        "visibility_offset": ["Good"],
    },
}


class EnvironmentalSimulator:
    """Generates deterministic environmental data for construction sites."""

    def generate_conditions(
        self,
        zone_type: str = "excavation",
        dt: datetime | None = None,
    ) -> dict[str, Any]:
        """Return a dict of environmental conditions for *zone_type*.

        Deterministic: same zone_type + datetime always yields the same result.
        """
        dt = dt or datetime.now(timezone.utc)
        base_seed = _seed_from_time("env", dt)

        scenario_key = _pick(SCENARIO_NAMES, base_seed)
        scenario = SCENARIOS[scenario_key]

        lo, hi = scenario["temp_range"]
        temperature = round(lo + (_seed_from_time("temp", dt) % (hi - lo + 1)), 1)

        lo, hi = scenario["humidity_range"]
        humidity = round(lo + (_seed_from_time("hum", dt) % (hi - lo + 1)), 1)

        lo, hi = scenario["wind_range"]
        wind_speed = round(lo + (_seed_from_time("wind", dt) % (hi - lo + 1)), 1)

        weather = scenario["weather"]
        visibility = scenario["visibility"]
        ground = scenario["ground_condition"]
        lighting = scenario["lighting_condition"]

        # Zone-specific overrides
        modifiers = ZONE_MODIFIERS.get(zone_type, {})
        if modifiers.get("ground_condition_offset"):
            ground = _pick(
                modifiers["ground_condition_offset"],
                _seed_from_time("gc_mod", dt),
            )
        if modifiers.get("visibility_offset"):
            visibility = _pick(
                modifiers["visibility_offset"],
                _seed_from_time("vis_mod", dt),
            )

        return {
            "scenario": scenario_key,
            "temperature_celsius": temperature,
            "humidity_percent": humidity,
            "wind_speed_kmh": wind_speed,
            "weather": weather,
            "visibility": visibility,
            "ground_condition": ground,
            "lighting_condition": lighting,
            "zone_type": zone_type,
            "timestamp": dt.isoformat(),
        }


# ---------------------------------------------------------------------------
# Equipment Simulator
# ---------------------------------------------------------------------------

EQUIPMENT_CATALOG: list[dict[str, Any]] = [
    {
        "name": "Excavator-01",
        "type": "excavator",
        "activities": ["excavation", "idle"],
        "base_duration_range": (60, 480),
    },
    {
        "name": "Dump Truck-01",
        "type": "dump_truck",
        "activities": ["hauling", "idle"],
        "base_duration_range": (30, 360),
    },
    {
        "name": "Crane-01",
        "type": "crane",
        "activities": ["lifting", "idle"],
        "base_duration_range": (45, 420),
    },
    {
        "name": "Bulldozer-01",
        "type": "bulldozer",
        "activities": ["grading", "idle"],
        "base_duration_range": (60, 400),
    },
    {
        "name": "Cement Mixer-01",
        "type": "cement_mixer",
        "activities": ["mixing", "idle"],
        "base_duration_range": (20, 300),
    },
]

STATUS_OPTIONS = ["active", "idle", "maintenance"]
MAINTENANCE_OPTIONS = ["operational", "due_soon", "overdue"]


class EquipmentSimulator:
    """Simulates equipment monitoring telemetry for construction sites."""

    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}
        self._cycle_counter: int = 0

    def _derive_state(
        self,
        equipment: dict[str, Any],
        dt: datetime,
    ) -> dict[str, Any]:
        """Derive deterministic state for a piece of equipment."""
        seed = _seed_from_time(equipment["name"], dt)

        status = _pick(STATUS_OPTIONS, seed)

        if status == "maintenance":
            activity = "idle"
            maintenance = _pick(
                ["due_soon", "overdue"],
                _seed_from_time(f"{equipment['name']}_maint", dt),
            )
        else:
            activity = _pick(equipment["activities"], seed)
            maintenance = _pick(MAINTENANCE_OPTIONS, seed)

        lo, hi = equipment["base_duration_range"]
        operating_duration = lo + (seed % (hi - lo + 1))

        nearby_workers = 0 + (seed % 12)

        return {
            "name": equipment["name"],
            "type": equipment["type"],
            "status": status,
            "activity": activity,
            "operating_duration_minutes": operating_duration,
            "maintenance_status": maintenance,
            "nearby_worker_count": nearby_workers,
        }

    def get_equipment_status(
        self,
        zone_id: str | None = None,
        dt: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return status of all equipment, optionally filtered by zone."""
        dt = dt or datetime.now(timezone.utc)
        results: list[dict[str, Any]] = []

        zone_map = {
            "Excavator-01": "zone_a",
            "Dump Truck-01": "zone_a",
            "Crane-01": "zone_c",
            "Bulldozer-01": "zone_a",
            "Cement Mixer-01": "zone_c",
        }

        for eq in EQUIPMENT_CATALOG:
            assigned_zone = zone_map.get(eq["name"], "zone_b")
            if zone_id and assigned_zone != zone_id:
                continue
            info = self._derive_state(eq, dt)
            info["zone"] = assigned_zone
            results.append(info)

        return results

    def simulate_changes(self) -> list[dict[str, Any]]:
        """Advance one simulation tick and return updated states."""
        self._cycle_counter += 1
        dt = datetime.now(timezone.utc)
        return self.get_equipment_status(dt=dt)


# ---------------------------------------------------------------------------
# Demo Data Generator
# ---------------------------------------------------------------------------

ZONES = [
    {"id": "zone_a", "name": "Excavation Zone A", "type": "excavation"},
    {"id": "zone_b", "name": "Material Storage Zone B", "type": "material_storage"},
    {"id": "zone_c", "name": "Building Structure Zone C", "type": "building_structure"},
]

HAZARD_TEMPLATES: list[dict[str, Any]] = [
    {
        "title": "Unsecured Edge Near Excavation",
        "severity": "critical",
        "category": "fall_hazard",
        "affected_zone": "zone_a",
        "description": "Workers operating within 2m of an unprotected excavation edge without barriers.",
    },
    {
        "title": "Overloaded Dump Truck",
        "severity": "high",
        "category": "equipment_hazard",
        "affected_zone": "zone_a",
        "description": "Dump Truck-01 carrying load exceeding rated capacity by 15%.",
    },
    {
        "title": "Crane Swing Radius Violation",
        "severity": "critical",
        "category": "equipment_hazard",
        "affected_zone": "zone_c",
        "description": "Crane-01 operating with personnel within the swing radius exclusion zone.",
    },
    {
        "title": "Wet Ground Slip Risk",
        "severity": "moderate",
        "category": "environmental_hazard",
        "affected_zone": "zone_b",
        "description": "Material Storage Zone B ground condition is wet with loose aggregate.",
    },
    {
        "title": "Poor Visibility in Excavation Zone",
        "severity": "high",
        "category": "environmental_hazard",
        "affected_zone": "zone_a",
        "description": "Fog reducing visibility below safe operating threshold for heavy equipment.",
    },
    {
        "title": "Cement Mixer Maintenance Overdue",
        "severity": "moderate",
        "category": "equipment_hazard",
        "affected_zone": "zone_c",
        "description": "Cement Mixer-01 past scheduled maintenance interval by 48 hours.",
    },
    {
        "title": "High Wind Advisory - Crane",
        "severity": "critical",
        "category": "environmental_hazard",
        "affected_zone": "zone_c",
        "description": "Wind speeds approaching operational limit for Crane-01 tower operations.",
    },
    {
        "title": "Worker Proximity to Active Excavation",
        "severity": "high",
        "category": "personnel_hazard",
        "affected_zone": "zone_a",
        "description": "8 workers detected within exclusion zone of active Excavator-01.",
    },
    {
        "title": "Material Stack Instability",
        "severity": "moderate",
        "category": "structural_hazard",
        "affected_zone": "zone_b",
        "description": "Steel reinforcement bars stacked above recommended height limit.",
    },
    {
        "title": "Inadequate Lighting in Zone C",
        "severity": "high",
        "category": "environmental_hazard",
        "affected_zone": "zone_c",
        "description": "Artificial lighting levels below OSHA minimum for detailed construction work.",
    },
]


class DemoDataGenerator:
    """Orchestrates all demo / simulated data for the platform."""

    def __init__(self) -> None:
        self.env_simulator = EnvironmentalSimulator()
        self.equipment_simulator = EquipmentSimulator()

    @property
    def project_info(self) -> dict[str, str]:
        return {
            "project_name": "Riverside Tower Complex",
            "project_id": "proj_riverside_001",
            "site_name": "Riverside Tower Main Site",
            "site_id": "site_riverside_main",
        }

    @property
    def zones(self) -> list[dict[str, str]]:
        return [z.copy() for z in ZONES]

    def generate_monitoring_event(
        self,
        site_id: str = "site_riverside_main",
        zones: list[dict[str, str]] | None = None,
        dt: datetime | None = None,
    ) -> dict[str, Any]:
        """Generate a single monitoring event with environmental + equipment data."""
        dt = dt or datetime.now(timezone.utc)
        zones = zones or ZONES

        env_data = {}
        for zone in zones:
            env_data[zone["id"]] = self.env_simulator.generate_conditions(
                zone_type=zone["type"], dt=dt
            )

        equipment_data = self.equipment_simulator.get_equipment_status(dt=dt)

        return {
            "site_id": site_id,
            "timestamp": dt.isoformat(),
            "environmental": env_data,
            "equipment": equipment_data,
        }

    def generate_hazard_analysis(
        self,
        site_id: str = "site_riverside_main",
        zones: list[dict[str, str]] | None = None,
        dt: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return a list of hazard dicts contextualised for the current conditions."""
        dt = dt or datetime.now(timezone.utc)
        zones = zones or ZONES

        env_snapshot: dict[str, dict[str, Any]] = {}
        for zone in zones:
            env_snapshot[zone["id"]] = self.env_simulator.generate_conditions(
                zone_type=zone["type"], dt=dt
            )

        equipment_snapshot = self.equipment_simulator.get_equipment_status(dt=dt)

        active_hazards: list[dict[str, Any]] = []
        for idx, template in enumerate(HAZARD_TEMPLATES):
            hazard_seed = _seed_from_time(f"hazard_{idx}", dt)

            # Only surface a subset of hazards per cycle (deterministic)
            if hazard_seed % 3 != 0:
                continue

            zone_env = env_snapshot.get(template["affected_zone"], {})
            triggering_factors = self._build_triggering_factors(
                template, zone_env, equipment_snapshot
            )

            active_hazards.append(
                {
                    **template,
                    "hazard_id": f"haz_{site_id}_{idx}",
                    "site_id": site_id,
                    "environmental_context": zone_env,
                    "triggering_factors": triggering_factors,
                    "detected_at": dt.isoformat(),
                }
            )

        return active_hazards

    def _build_triggering_factors(
        self,
        hazard: dict[str, Any],
        zone_env: dict[str, Any],
        equipment: list[dict[str, Any]],
    ) -> list[str]:
        """Determine which environmental / equipment factors contribute to this hazard."""
        factors: list[str] = []

        category = hazard.get("category", "")

        if category == "environmental_hazard":
            if zone_env.get("weather") in ("Rainy", "Stormy"):
                factors.append(f"Weather: {zone_env['weather']}")
            if zone_env.get("visibility") in ("Poor", "Very Poor"):
                factors.append(f"Visibility: {zone_env['visibility']}")
            if zone_env.get("ground_condition") in ("Wet", "Muddy", "Icy"):
                factors.append(f"Ground: {zone_env['ground_condition']}")
            if zone_env.get("wind_speed_kmh", 0) > 35:
                factors.append(f"Wind speed: {zone_env['wind_speed_kmh']} km/h")
            if zone_env.get("lighting_condition") in ("Poor", "Dark"):
                factors.append(f"Lighting: {zone_env['lighting_condition']}")

        elif category == "equipment_hazard":
            for eq in equipment:
                if eq["name"] in hazard.get("title", ""):
                    factors.append(f"Equipment status: {eq['status']}")
                    if eq["maintenance_status"] != "operational":
                        factors.append(f"Maintenance: {eq['maintenance_status']}")
                    factors.append(f"Activity: {eq['activity']}")
                    factors.append(f"Workers nearby: {eq['nearby_worker_count']}")

        elif category == "personnel_hazard":
            for eq in equipment:
                if eq["nearby_worker_count"] > 5:
                    factors.append(
                        f"{eq['name']}: {eq['nearby_worker_count']} workers in proximity"
                    )

        if not factors:
            factors.append("Combination of site conditions exceeds safe threshold")

        return factors

    def get_risk_scenario(
        self,
        dt: datetime | None = None,
    ) -> dict[str, Any]:
        """Return a complete risk scenario bundle for the demo."""
        dt = dt or datetime.now(timezone.utc)

        monitoring = self.generate_monitoring_event(dt=dt)
        hazards = self.generate_hazard_analysis(dt=dt)

        severity_counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
        for h in hazards:
            sev = h.get("severity", "low")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        overall_risk = "low"
        if severity_counts["critical"] > 0:
            overall_risk = "critical"
        elif severity_counts["high"] > 0:
            overall_risk = "high"
        elif severity_counts["moderate"] > 0:
            overall_risk = "moderate"

        return {
            "scenario_timestamp": dt.isoformat(),
            **self.project_info,
            "zones": self.zones,
            "monitoring_event": monitoring,
            "active_hazards": hazards,
            "hazard_summary": {
                "total_hazards": len(hazards),
                "severity_breakdown": severity_counts,
                "overall_risk_level": overall_risk,
            },
        }
