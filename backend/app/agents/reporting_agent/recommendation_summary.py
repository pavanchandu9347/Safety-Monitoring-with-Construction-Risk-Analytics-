"""Prioritized actions for the Reporting Agent (Milestone 4).

Actions are drawn from real persisted recommendations (site risk agent rows,
compliance/insurance assessment recommendation fields and per-violation
mitigations). They are ranked by priority only set in the persisted data —
nothing is invented.
"""

from __future__ import annotations

from typing import Any, Optional

_PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "LOWEST": 4}


def prioritized_actions(ctx: dict) -> list[dict]:
    recs = ctx.get("recommendations") or []
    recs = sorted(
        recs,
        key=lambda r: _PRIORITY_RANK.get(str(r.get("priority") or "MEDIUM").upper(), 2),
    )

    actions = []
    for rec in recs:
        actions.append(
            {
                "priority": str(rec.get("priority") or "MEDIUM").upper(),
                "source": rec.get("source", ""),
                "title": rec.get("title", ""),
                "description": rec.get("description", ""),
                "category": rec.get("category") or rec.get("hazard_type") or "",
            }
        )
    return actions