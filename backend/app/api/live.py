"""
Live analysis API: start/stop/status + WebSocket feed + MJPEG annotated stream.

Endpoints (all under /api):
  GET  /sites/{site_id}/live/status
  POST /sites/{site_id}/live/start     body: {video_path?, conf?}
  POST /sites/{site_id}/live/stop
  WS   /ws/sites/{site_id}/live        (note: no /api prefix, matches client)
  GET  /sites/{site_id}/live/video     (MJPEG annotated frames)

The WebSocket sends structured JSON "metrics" snapshots derived from real YOLO
detections. The MJPEG stream carries the annotated video separately so raw
frames are never serialised as JSON.
"""

from __future__ import annotations

import asyncio
import queue
import sys
import os
import time
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.live import pipeline as pipeline_mod
from app.config import default_video_source

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_CONF = float(os.environ.get("YOLO_CONFIDENCE", "0.45"))


class StartRequest(BaseModel):
    video_path: str = ""
    conf: float | None = None


def _resolve_source(site_id: str, video_path: str = "") -> str | int:
    if video_path:
        return video_path
    source = default_video_source()
    if isinstance(source, str) and source.isdigit():
        return int(source)
    return source


@router.get("/sites/{site_id}/live/status")
def live_status(site_id: str):
    return pipeline_mod.manager.status(site_id)


@router.post("/sites/{site_id}/live/start")
def live_start(site_id: str, req: StartRequest | None = None):
    req = req or StartRequest()
    source = _resolve_source(site_id, req.video_path)
    conf = req.conf if req.conf is not None else DEFAULT_CONF
    return pipeline_mod.manager.start(site_id, source, conf=conf)


@router.post("/sites/{site_id}/live/stop")
def live_stop(site_id: str):
    return pipeline_mod.manager.stop(site_id)


@router.websocket("/ws/sites/{site_id}/live")
async def ws_live(websocket: WebSocket, site_id: str):
    await websocket.accept()
    pipe = pipeline_mod.manager.get(site_id)
    if pipe is None:
        # Create a stopped placeholder just so a client can connect and learn
        # the pipeline is not running without fabricating data.
        pipe = pipeline_mod.LivePipeline(site_id, DEFAULT_VIDEO_SOURCE, conf=DEFAULT_CONF)
        pipeline_mod._PIPELINES[site_id] = pipe

    q: queue.Queue = queue.Queue(maxsize=50)
    pipe.subscribe(q)

    try:
        while True:
            try:
                snapshot = await asyncio.to_thread(q.get, True, 0.5)
            except queue.Empty:
                # Fall through and re-send latest so the client knows the state.
                snapshot = pipe.latest_snapshot or {"status": pipe.status}
            try:
                await websocket.send_json(snapshot)
            except Exception:  # noqa: BLE001
                break
    except WebSocketDisconnect:
        pass
    finally:
        pipe.unsubscribe(q)


@router.get("/sites/{site_id}/live/video")
def live_video(site_id: str):
    pipe = pipeline_mod.manager.get(site_id)

    def gen():
        boundary = b"frame"
        while True:
            if pipe is None or pipe.latest_jpeg is None:
                # No frames yet; keep the stream open without faking data.
                time.sleep(0.2)
                continue
            jpeg = pipe.latest_jpeg
            yield (
                b"--" + boundary + b"\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            )
            time.sleep(0.1)

    return StreamingResponse(
        gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
