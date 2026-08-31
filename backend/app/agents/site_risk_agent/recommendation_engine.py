from __future__ import annotations


class RecommendationEngine:
    """Generates actionable recommendations from hazards and risk scores."""

    PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

    HAZARD_RECOMMENDATIONS: dict[str, dict] = {
        "equipment_proximity": {
            "title": "Enforce equipment exclusion zones",
            "description": (
                "Establish and enforce physical exclusion zones around operating "
                "heavy equipment. Ensure no personnel enter the exclusion zone "
                "without proper signalling and spotters."
            ),
        },
        "equipment_maintenance": {
            "title": "Schedule emergency maintenance",
            "description": (
                "Remove equipment with overdue maintenance from active operation. "
                "Conduct a thorough inspection and complete required maintenance "
                "before returning to service."
            ),
        },
        "equipment_density": {
            "title": "Reduce equipment density in zone",
            "description": (
                "Redistribute equipment across multiple zones to reduce congestion. "
                "Implement staggered scheduling to limit simultaneous operation "
                "of heavy equipment in the same area."
            ),
        },
        "poor_visibility": {
            "title": "Suspend or restrict active operations",
            "description": (
                "Reduce or suspend active equipment operations during poor "
                "visibility conditions. If operations must continue, deploy "
                "additional spotters and increase lighting where possible."
            ),
        },
        "adverse_weather": {
            "title": "Activate weather contingency plan",
            "description": (
                "Implement weather contingency protocols. Secure loose materials "
                "and equipment. Consider suspending outdoor operations if "
                "conditions worsen."
            ),
        },
        "high_wind": {
            "title": "Suspend crane and lifting operations",
            "description": (
                "Immediately suspend crane and lifting operations when wind "
                "speeds exceed safe thresholds. Secure all suspended loads and "
                "lower crane booms to neutral position."
            ),
        },
        "extreme_temperature": {
            "title": "Implement thermal safety protocols",
            "description": (
                "Increase rest break frequency and ensure adequate hydration "
                "stations and warming areas. Monitor personnel for signs of "
                "heat stress or cold-related illness."
            ),
        },
        "wet_ground": {
            "title": "Implement slip prevention measures",
            "description": (
                "Deploy anti-slip mats and drainage solutions. Require "
                "appropriate footwear and reduce vehicle speeds on wet surfaces."
            ),
        },
        "icy_ground": {
            "title": "Apply ice mitigation and restrict access",
            "description": (
                "Apply salt or grit to icy surfaces immediately. Restrict "
                "foot traffic in affected areas. Use only essential personnel "
                "until surfaces are treated."
            ),
        },
        "crane_high_wind": {
            "title": "Secure cranes for high wind",
            "description": (
                "Immediately secure all cranes: lower loads, disengage slew "
                "brakes per manufacturer guidance, and move to safe park "
                "position. Do not resume until wind drops below threshold."
            ),
        },
        "low_lighting": {
            "title": "Deploy additional site lighting",
            "description": (
                "Install temporary lighting in poorly lit areas. Require "
                "high-visibility PPE for all personnel and restrict vehicle "
                "speeds in low-light zones."
            ),
        },
        "ground_unstable": {
            "title": "Restrict access to unstable ground",
            "description": (
                "Cordon off areas with unstable ground. Conduct a geotechnical "
                "assessment before allowing further work in affected zones."
            ),
        },
    }

    def generate(self, hazards: list[dict], risk_scores: dict) -> list[dict]:
        recommendations: list[dict] = []
        seen_types: set[str] = set()

        for hazard in hazards:
            hazard_type = hazard.get("hazard_type", "")
            if hazard_type in seen_types:
                continue
            seen_types.add(hazard_type)

            rec = self._map_hazard_to_recommendation(hazard)
            if rec is not None:
                recommendations.append(rec)

        recommendations = self._add_score_based_recommendations(
            risk_scores, recommendations, seen_types
        )

        recommendations.sort(key=lambda r: self.PRIORITY_ORDER.get(r["priority"], 3))
        return recommendations

    # ── Private helpers ────────────────────────────────────────────────────

    def _map_hazard_to_recommendation(self, hazard: dict) -> dict | None:
        hazard_type = hazard.get("hazard_type", "")
        severity = hazard.get("severity", "LOW").upper()

        template = self.HAZARD_RECOMMENDATIONS.get(hazard_type)
        if template is None:
            return {
                "title": f"Address {hazard_type.replace('_', ' ')} hazard",
                "description": hazard.get("recommended_mitigation", "Investigate and mitigate."),
                "priority": severity,
                "hazard_type": hazard_type,
                "related_hazard_id": hazard.get("id"),
            }

        return {
            "title": template["title"],
            "description": template["description"],
            "priority": severity,
            "hazard_type": hazard_type,
            "related_hazard_id": hazard.get("id"),
        }

    def _add_score_based_recommendations(
        self, risk_scores: dict, recommendations: list[dict], seen_types: set[str],
    ) -> list[dict]:
        env = risk_scores.get("environmental", {})
        eq = risk_scores.get("equipment", {})
        sc = risk_scores.get("site_condition", {})
        act = risk_scores.get("activity", {})

        if env.get("score", 0) >= 50 and "adverse_weather" not in seen_types:
            recommendations.append({
                "title": "Increase environmental monitoring frequency",
                "description": (
                    "Environmental risk is elevated. Increase monitoring "
                    "intervals and prepare to implement weather contingency plans."
                ),
                "priority": "HIGH" if env.get("score", 0) >= 75 else "MEDIUM",
                "hazard_type": "adverse_weather",
                "related_hazard_id": None,
            })

        if eq.get("score", 0) >= 50 and "equipment_maintenance" not in seen_types:
            recommendations.append({
                "title": "Conduct comprehensive equipment audit",
                "description": (
                    "Equipment risk is elevated. Perform a comprehensive audit of "
                    "all active equipment including maintenance status and "
                    "operator qualifications."
                ),
                "priority": "HIGH" if eq.get("score", 0) >= 75 else "MEDIUM",
                "hazard_type": "equipment_maintenance",
                "related_hazard_id": None,
            })

        overall = risk_scores.get("overall", {})
        if overall.get("overall_score", 0) >= 75:
            recommendations.insert(0, {
                "title": "Activate emergency site safety protocol",
                "description": (
                    "Overall site risk is CRITICAL. Activate emergency safety "
                    "protocol. Suspend non-essential operations and conduct "
                    "an immediate safety briefing for all personnel."
                ),
                "priority": "CRITICAL",
                "hazard_type": "site_safety",
                "related_hazard_id": None,
            })

        return recommendations
