"""Inspection tracker — honest inspection status for the site.

An inspection is ``COMPLETED`` only when a real record exists (``last_inspection``
set). Without a record the status is ``OVERDUE`` (due date passed), ``DUE``
(not yet due) or ``NOT_AVAILABLE``. No completion is ever fabricated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def analyze(inspections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute statuses for required inspections from the given records."""
    now = datetime.now(timezone.utc)
    evaluated: List[Dict[str, Any]] = []
    overdue = 0
    due = 0
    completed = 0

    for insp in inspections:
        status = "NOT_AVAILABLE"
        due_date = insp.get("due_date")
        last = insp.get("last_inspection")
        evidence = insp.get("evidence", "")

        due_aware = _aware(due_date) if isinstance(due_date, datetime) else None
        last_aware = _aware(last) if isinstance(last, datetime) else None

        if last_aware:
            status = "COMPLETED"
            completed += 1
            evidence = evidence or "Completed inspection record available."
        else:
            if insp.get("status") == "COMPLETED":
                # A record claims completion but carries no date — keep honest.
                status = "NOT_AVAILABLE"
                evidence = "Inspection record references no completion date."
            elif due_aware and due_aware < now:
                status = "OVERDUE"
                overdue += 1
            elif due_aware:
                status = "DUE"
                due += 1

        evaluated.append({
            "id": insp.get("id"),
            "site_id": insp.get("site_id"),
            "inspection_type": insp.get("inspection_type", ""),
            "description": insp.get("description", ""),
            "due_date": (
                due_aware.isoformat() if isinstance(due_aware, datetime)
                else due_date.isoformat() if hasattr(due_date, "isoformat")
                else due_date
            ),
            "last_inspection": (
                last_aware.isoformat() if isinstance(last_aware, datetime)
                else last.isoformat() if hasattr(last, "isoformat")
                else last
            ),
            "status": status,
            "evidence": evidence,
        })

    return {
        "inspections": evaluated,
        "total": len(evaluated),
        "overdue": overdue,
        "due": due,
        "completed": completed,
        "note": (
            "Inspection status reflects only records available to the platform; "
            "no completed inspection is assumed."
        ),
    }


def is_fully_verified(result: Dict[str, Any]) -> bool:
    return result["total"] > 0 and result["overdue"] == 0 and result["completed"] == result["total"]