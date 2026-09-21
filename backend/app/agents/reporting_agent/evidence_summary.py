"""Evidence summary section for the Reporting Agent (Milestone 4).

Surfaces exactly which real evidence was used so report readers can trace
every claim back to the analysis it came from.
"""

from __future__ import annotations

from typing import Any, Optional


def build(ctx: dict) -> dict:
    evidence = ctx.get("evidence_summary") or {}
    quality = ctx.get("data_quality") or {}
    available = quality.get("available_agents") or {}

    return {
        "video": evidence.get("video", {}),
        "counts": evidence.get("counts", {}),
        "inspections": evidence.get("inspections", []),
        "data_quality": {
            "status": quality.get("status", "PARTIAL"),
            "available_agents": available,
            "insufficient_dimensions": quality.get("insufficient_dimensions", []),
            "note": quality.get("note", ""),
        },
    }