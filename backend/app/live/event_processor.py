"""
Safety event processor.

Converts real YOLO detection-derived worker PPE status into human-readable
safety events, debounced so a person who remains without a helmet does not
spawn an alert on every frame.

A worker is identified by a stable per-session id (index within the current
detection set, re-anchored by nearest person box across windows). When their
status changes (e.g. goes non-compliant, or a new violation type appears), a new
event is emitted and timestamped. Repeating identical states are coalesced and
only re-emitted after a cooldown window.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

# Minimum seconds between repeated events of the same kind for the same worker.
EVENT_COOLDOWN_SECONDS = 4.0


class SafetyEventProcessor:
    """Debounces and persists (in-memory) safety events derived from detections."""

    def __init__(self, cooldown: float = EVENT_COOLDOWN_SECONDS) -> None:
        self.cooldown = cooldown
        # worker_key -> {last_type, last_status, last_ts}
        self._state: Dict[str, Dict[str, Any]] = {}
        self._events: List[Dict[str, Any]] = []

    def reset(self) -> None:
        """Clear tracked worker state and buffered events (start/stop)."""
        self._state.clear()
        self._events.clear()

    def process(self, workers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Consume a per-worker list (from real detections) and emit new events.

        Args:
            workers: [{worker_id, ppe_status, missing_ppe:[...], ...}]

        Returns:
            New events emitted for this window:
            [{id, timestamp, worker_id, event_type, message, severity}]
        """
        now = datetime.now(timezone.utc)
        new_events: List[Dict[str, Any]] = []

        for w in workers or []:
            worker_id = w.get("worker_id", "unknown")
            status = w.get("ppe_status", "compliant")
            missing = sorted(w.get("missing_ppe", []) or [])

            if status == "compliant":
                event_type = "PPE_COMPLIANT"
                message = f"Worker {worker_id} — PPE compliant"
                severity = "LOW"
            elif "helmet" in missing:
                event_type = "NO_HELMET"
                message = f"Worker {worker_id} — helmet violation"
                severity = "HIGH"
            elif "vest" in missing:
                event_type = "NO_VEST"
                message = f"Worker {worker_id} — vest violation"
                severity = "HIGH"
            else:
                event_type = "OTHER_PPE_VIOLATION"
                message = (
                    f"Worker {worker_id} — missing {', '.join(x.replace('_', ' ') for x in missing) or 'PPE'}"
                )
                severity = "MEDIUM"

            prev = self._state.get(worker_id)
            due = (
                prev is None
                or prev.get("event_type") != event_type
            )
            if not due and prev:
                elapsed = (now - datetime.fromisoformat(prev["timestamp"])).total_seconds()
                due = elapsed >= self.cooldown

            if due:
                event = {
                    "id": f"ev_{worker_id}_{int(now.timestamp() * 1000)}",
                    "timestamp": now.isoformat(),
                    "worker_id": worker_id,
                    "event_type": event_type,
                    "message": message,
                    "severity": severity,
                }
                new_events.append(event)
                self._events.append(event)
                self._state[worker_id] = {
                    "event_type": event_type,
                    "timestamp": now.isoformat(),
                }

        # Keep the in-memory buffer bounded.
        if len(self._events) > 200:
            self._events = self._events[-200:]

        return new_events

    @property
    def events(self) -> List[Dict[str, Any]]:
        """Recent events buffer (newest last)."""
        return list(self._events)

    @property
    def recent(self) -> List[Dict[str, Any]]:
        """Recent events, newest first."""
        return list(reversed(self._events[-20:]))
