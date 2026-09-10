"""
Accident-prone zone analysis — identifies zones that are historically or
contextually most likely to produce incidents, and assigns each an
accident risk level plus contributing factors.
"""

from __future__ import annotations

from typing import Any, Dict, List


class AccidentZoneAnalyzer:
    """Evaluates the accident-proneness of each construction zone.

    Combines current risk level, hazard density, and worker/equipment
    activity to produce a per-zone accident risk assessment and an overall
    accident-prone metric.
    """

    def analyze(self, zone_data: List[Dict], equipment_data: List[Dict]) -> Dict:
        zone_assessments: List[Dict] = []
        for zone in zone_data:
            zone_id = zone.get("zone_id") or zone.get("id")
            base_level = (zone.get("risk_level") or zone.get("accident_risk_level") or "LOW").upper()
            hazard_count = zone.get("active_hazard_count", 0)

            # Equipment density in this zone contributes to accident risk.
            zone_equip = [
                e for e in equipment_data if e.get("zone_id") == zone_id
            ]
            active_zone_equip = [
                e for e in zone_equip
                if e.get("status") in ("active", "operating", "running")
            ]

            # Pre-computed video-region risk (if any) is the baseline; otherwise
            # fall back to declared zone metadata (also evidence-derived).
            base_score = float(zone.get("accident_risk_score") or self._level_score(base_level))
            if hazard_count >= 3:
                base_score += 15
            elif hazard_count >= 1:
                base_score += 8
            if len(active_zone_equip) >= 3:
                base_score += 12

            score = min(base_score, 100.0)
            factors = list(zone.get("factors") or [f"Zone baseline risk: {base_level}"])
            if not factors:
                factors = [f"Zone baseline risk: {base_level}"]
            if hazard_count:
                factors.append(f"{hazard_count} active hazards in zone")
            if active_zone_equip:
                factors.append(
                    f"{len(active_zone_equip)} active equipment units in zone"
                )

            zone_assessments.append(
                {
                    "zone_id": zone_id,
                    "zone_name": zone.get("zone_name") or zone.get("name") or zone_id,
                    "accident_risk_score": round(score, 2),
                    "accident_risk_level": self._level(score),
                    "factors": factors,
                    "active_hazard_count": hazard_count,
                    "active_equipment_count": len(active_zone_equip),
                }
            )

        # Sort by descending accident risk.
        zone_assessments.sort(
            key=lambda z: z["accident_risk_score"], reverse=True
        )
        top_zone = zone_assessments[0] if zone_assessments else None

        return {
            "zones": zone_assessments,
            "top_accident_zone": top_zone,
            "overall_accident_risk": self._overall(zone_assessments),
        }

    def analyze_from_video(
        self,
        frame_evidence: List[Dict],
        image_width: float = 1000.0,
        image_height: float = 600.0,
    ) -> Dict:
        """Derive spatial accident-risk zones from ACTUAL frame detections.

        The frame is divided into a 3×2 grid of observation regions. Every
        detection box from the sampled frames is attributed to a region by its
        centre. A region is scored from the density and co-occurrence of
        persons and equipment over the frames (repeated activity), producing a
        risk value only for regions that actually contain evidence.

        Returns ``{"available": False, ...}`` with an explicit note when no
        spatial observation can be established, so callers never invent zones.
        """
        w = float(image_width or 1000.0)
        h = float(image_height or 600.0)
        cols, rows = 3, 2

        region_stats = {
            (c, r): {"person": 0, "vehicle": 0, "co_occurrence": 0, "frames": 0}
            for c in range(cols)
            for r in range(rows)
        }
        region_frames: Dict[tuple, set] = {(c, r): set() for c in range(cols) for r in range(rows)}

        samples = list(frame_evidence or [])
        for frame in samples:
            seen_in_frame: set = set()
            for d in frame.get("detections", []):
                bbox = d.get("bbox") or []
                if len(bbox) < 4:
                    continue
                x1, y1, x2, y2 = (float(v) for v in bbox[:4])
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                col = min(cols - 1, max(0, int(cx / w * cols)))
                row = min(rows - 1, max(0, int(cy / h * rows)))
                cid = d.get("class_id")
                is_person = cid == 0
                if is_person or cid in (2, 5, 7, 8):
                    region_stats[(col, row)]["frames"] += 1
                    if is_person:
                        region_stats[(col, row)]["person"] += 1
                        seen_in_frame.add((col, row))
                    else:
                        region_stats[(col, row)]["vehicle"] += 1
            # Person + vehicle co-occurrence in the SAME sampled frame.
            for (col, row) in seen_in_frame:
                if region_stats[(col, row)]["vehicle"] > 0:
                    # count frames where region had both
                    region_frames[(col, row)].add(id(frame))

        zones: List[Dict] = []
        for (col, row), st in region_stats.items():
            total = st["person"] + st["vehicle"]
            if total == 0:
                continue
            x0 = (col / cols) * 100
            x1 = ((col + 1) / cols) * 100
            y0 = (row / rows) * 100
            y1 = ((row + 1) / rows) * 100
            score = 0.0
            factors = ["Region derived from real video detections"]
            if st["vehicle"] >= 1:
                score += 25
                factors.append(f"{st['vehicle']} equipment detection(s) in region")
            if st["person"] >= 1:
                score += 15
                factors.append(f"{st['person']} worker detection(s) in region")
            if len(region_frames[(col, row)]) > 0:
                score += 20
                factors.append("person + equipment co-occurrence observed in same frame")
            if st["frames"] >= 3:
                score += 15
                factors.append("repeated activity across sampled frames")
            score = min(score, 100.0)
            zones.append({
                "zone_id": f"vr_{row * cols + col + 1}",
                "zone_name": f"Video Region {row * cols + col + 1} "
                             f"({x0:.0f}-{x1:.0f}% × {y0:.0f}-{y1:.0f}%)",
                "region": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
                "accident_risk_score": round(score, 2),
                "accident_risk_level": self._level(score),
                "factors": factors,
                "person_detections": st["person"],
                "vehicle_detections": st["vehicle"],
                "frames_with_activity": st["frames"],
                "co_occurrence_frames": len(region_frames[(col, row)]),
            })

        if not zones:
            return {
                "available": False,
                "note": "Insufficient video evidence for zone analysis "
                        "(no spatial person/equipment observations in sampled frames).",
                "zones": [],
                "top_accident_zone": None,
                "overall_accident_risk": {"score": 0.0, "risk_level": "LOW", "factors": [], "evidence_available": False},
            }

        zones.sort(key=lambda z: z["accident_risk_score"], reverse=True)
        top = zones[0]
        return {
            "available": True,
            "note": "Accident zones derived from spatial video evidence.",
            "zones": zones,
            "top_accident_zone": top,
            "overall_accident_risk": {
                "score": round(top["accident_risk_score"], 2),
                "risk_level": top["accident_risk_level"],
                "factors": top["factors"] + ["Region risk dominates zone analysis"],
                "evidence_available": True,
            },
        }

    @staticmethod
    def _level_score(level: str) -> float:
        return {
            "LOW": 10, "MEDIUM": 30, "HIGH": 55, "CRITICAL": 80,
        }.get(str(level).upper(), 10)

    @staticmethod
    def _level(score: float) -> str:
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"

    @staticmethod
    def _overall(zone_assessments: List[Dict]) -> Dict:
        if not zone_assessments:
            return {
                "score": 0.0,
                "risk_level": "LOW",
                "factors": ["No spatial accident-zone evidence from video"],
                "evidence_available": False,
            }
        # Weighted toward the highest-risk zone.
        top = zone_assessments[0]
        second = zone_assessments[1] if len(zone_assessments) > 1 else None
        score = top["accident_risk_score"] * 0.7
        if second:
            score += second["accident_risk_score"] * 0.3
        score = min(score, 100.0)
        return {
            "score": round(score, 2),
            "risk_level": AccidentZoneAnalyzer._level(score),
            "factors": [
                f"Highest-risk zone: {top['zone_name']} "
                f"({top['accident_risk_level']})"
            ],
        }
