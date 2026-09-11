"""Policy violation detector — consumes existing project findings.

Takes the real safety violations, hazards and alerts already produced by the
Milestone 2 pipeline and reshapes them into policy-violation records with a
compliance category. No new evidence is fabricated; every record references
its originating analysis via ``analysis_id``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

_CATEGORY_BY_TYPE = [
    ("ppe", "PPE"),
    ("unsafe", "Worker Safety"),
    ("swing", "Worker Safety"),
    ("proximity", "Worker Safety"),
    ("worker_density", "Worker Safety"),
    ("equipment", "Equipment Safety"),
    ("zone", "Equipment Safety"),
    ("archaeological", "Site Safety"),
    ("housekeeping", "Site Safety"),
]


def _category_for(violation_type: str) -> str:
    vt = str(violation_type or "").lower()
    for needle, category in _CATEGORY_BY_TYPE:
        if needle in vt:
            return category
    return "Site Safety"


def detect(
    violations: List[Dict[str, Any]],
    hazards: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Map real safety violations/hazards into compliance policy violations."""
    now = datetime.now(timezone.utc)
    records: List[Dict[str, Any]] = []
    seen: set = set()

    def _add(item: Dict[str, Any], vtype: str) -> None:
        key = (vtype, str(item.get("description", ""))[:120])
        if key in seen:
            return
        seen.add(key)
        records.append({
            "finding_id": str(uuid.uuid4()),
            "site_id": item.get("site_id") or context.get("site_id"),
            "analysis_id": item.get("analysis_id") or context.get("analysis_id"),
            "category": _category_for(vtype),
            "description": item.get("description", ""),
            "severity": item.get("severity", "LOW"),
            "status": item.get("status", "open"),
            "evidence": item.get("evidence", ""),
            "source": item.get("source", "video_vision"),
            "timestamp": item.get("timestamp") or now.isoformat(),
        })

    for v in violations:
        _add(v, str(v.get("violation_type", "violation")))
    for h in hazards:
        _add(h, str(h.get("hazard_type", "hazard")))
    return records


def open_violation_count(violations: List[Dict[str, Any]]) -> int:
    """Number of real open safety violations feeding the compliance state."""
    if not violations:
        return 0
    if isinstance(violations[0], str):
        return sum(1 for _ in violations)
    return sum(1 for v in violations if str(v.get("status", "open")).lower() == "open")