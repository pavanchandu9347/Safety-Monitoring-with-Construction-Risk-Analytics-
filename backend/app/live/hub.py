"""Per-site broadcast hub for live notification events (Milestone 4).

WebSocket clients subscribed to a site receive analysis metrics AND real
notification events over the same socket. Notifications are produced by the
notification service (from genuine analysis output) and pushed to every
subscriber queue here. Uses thread-safe ``queue.Queue`` objects so broadcasts
can originate from the analysis/notification path without an event loop.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

_MAX_QUEUE = 100


class NotificationHub:
    def __init__(self) -> None:
        self._subs: dict[str, set[queue.Queue]] = defaultdict(set)
        self._lock = threading.Lock()

    def subscribe(self, site_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=_MAX_QUEUE)
        with self._lock:
            self._subs[site_id].add(q)
        return q

    def unsubscribe(self, site_id: str, q: queue.Queue) -> None:
        with self._lock:
            subs = self._subs.get(site_id)
            if subs:
                subs.discard(q)
                if not subs:
                    self._subs.pop(site_id, None)

    def broadcast(self, site_id: str, payload: dict[str, Any]) -> int:
        """Push ``payload`` to every subscriber; drop-oldest if a queue is full."""
        with self._lock:
            targets = list(self._subs.get(site_id, ()))
        dropped = 0
        for q in targets:
            try:
                q.put_nowait(payload)
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except (queue.Empty, queue.Full):
                    pass
                dropped += 1
        if dropped:
            logger.warning("notification hub: dropped %d subscriber(s) at full queue", dropped)
        return len(targets)


NOTIFICATION_HUB = NotificationHub()