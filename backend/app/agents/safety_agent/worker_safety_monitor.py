"""
Worker safety monitoring — evaluates worker count, zone hazards, and
behavioral risk to produce a worker safety score with explainable factors.
"""

from __future__ import annotations

from typing import Any, Dict, List


class WorkerSafetyMonitor:
    """Assesses worker safety conditions across construction zones.

    Produces a 0-100 worker_safety_score based on the number of workers
    active per zone, proximity to equipment, and detected unsafe behavior.
    """

    def analyze(
        self,
        equipment_data: List[Dict],
        detected_objects: List[Dict],
        zone_data: List[Dict],
        unsafe_events: List[Dict],
    ) -> Dict:
        score = 0.0
        factors: List[str] = []

        worker_count = self._count_workers(detected_objects, equipment_data)
        factors.append(f"Workers tracked: {worker_count}")

        # Score from worker density near equipment.
        near = [
            e.get("nearby_worker_count", 0)
            for e in equipment_data
            if e.get("status") in ("active", "operating", "running")
        ]
        total_near = sum(near)
        if total_near >= 12:
            score += 35
            factors.append(
                f"High worker density near active equipment ({total_near} workers)"
            )
        elif total_near >= 7:
            score += 20
            factors.append("Elevated worker density near active equipment")

        # Score from unsafe behavior events.
        unsafe_count = len(unsafe_events)
        if unsafe_count > 0:
            safe_high = sum(1 for e in unsafe_events if e.get("severity") == "HIGH")
            score += min(30 + safe_high * 10, 50)
            factors.append(f"Unsafe behavior events: {unsafe_count}")

        # Score from high-risk zones.
        high_zones = [z for z in zone_data if z.get("risk_level") == "HIGH"]
        critical_zones = [z for z in zone_data if z.get("risk_level") == "CRITICAL"]
        if critical_zones:
            score += 30
            factors.append(f"{len(critical_zones)} critical-risk zones active")
        elif high_zones:
            score += 15
            factors.append(f"{len(high_zones)} high-risk zones active")

        score = min(score, 100.0)
        evidence_available = (
            worker_count > 0
            or total_near > 0
            or unsafe_count > 0
            or bool(high_zones)
            or bool(critical_zones)
        )
        if not evidence_available:
            factors.append(
                "No worker-safety evidence recoverable from current video frames"
            )
        return {
            "score": round(score, 2),
            "risk_level": self._level(score),
            "factors": factors,
            "worker_count": worker_count,
            "workers_near_equipment": total_near,
            "evidence_available": evidence_available,
        }

    @staticmethod
    def _count_workers(detected_objects: List[Dict], equipment_data: List[Dict]) -> int:
        cv_count = sum(
            1 for d in detected_objects if d.get("class_id") == 0
        )
        equip_count = sum(
            e.get("nearby_worker_count", 0)
            for e in equipment_data
            if e.get("status") in ("active", "operating", "running")
        )
        # Combine CV detections (if any) with equipment worker counts.
        return max(cv_count, equip_count)

    @staticmethod
    def _level(score: float) -> str:
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"
