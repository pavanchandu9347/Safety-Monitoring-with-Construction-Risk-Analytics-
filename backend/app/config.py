"""Runtime configuration for the unified video-analysis pipeline.

All settings are env-overridable (see ``backend/.env.example``). The pipeline
uses ONE construction-site video as its single primary input: it is discovered
from the project folder (or provided by the caller), sampled for real YOLO/PPE
inference, and the resulting evidence feeds every downstream agent.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")

VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v")

# Video files are copied/kept here on upload. Stored videos live here too.
VIDEO_STORAGE_PATH = Path(
    os.environ.get("VIDEO_STORAGE_PATH", str(BACKEND_DIR / "data" / "videos"))
)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Number of video frames to skip between analysis samples (~2fps at 30fps video).
FRAME_SAMPLE_RATE: int = _env_int("FRAME_SAMPLE_RATE", 15)
# Maximum number of sampled frames analyzed per video pass.
MAX_FRAMES: int = _env_int("MAX_FRAMES", 30)
# Downscale width before inference (matches the live pipeline).
PROCESS_WIDTH: int = _env_int("PROCESS_WIDTH", 1280)
# Confidence threshold for YOLO detections.
CONFIDENCE_THRESHOLD: float = float(
    os.environ.get("CONFIDENCE_THRESHOLD", os.environ.get("YOLO_CONFIDENCE", "0.45"))
)
# Optional explicit default video path. When empty the project folder is scanned.
DEFAULT_VIDEO_SOURCE: str = os.environ.get("VIDEO_SOURCE", "").strip()

# Reserved directories to skip while discovering videos in the project folder.
_SKIP_DIRS = frozenset(
    {"node_modules", ".git", "venv", "data", "__pycache__", ".venv", "dist", "build"}
)

_VIDEO_CACHE: list[dict] | None = None


def ensure_storage() -> Path:
    VIDEO_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    return VIDEO_STORAGE_PATH


def discover_videos() -> list[dict]:
    """Discover construction-site videos inside the project folder.

    Scans the repository root (excluding code/vendor directories) plus the video
    storage folder. Returns a list of ``{name, path, size_mb}`` records. When a
    single video exists anywhere in the project it is the unambiguous primary
    input; if several exist the frontend offers a selector.
    """
    global _VIDEO_CACHE
    if _VIDEO_CACHE is not None:
        return [dict(v) for v in _VIDEO_CACHE]

    found: list[dict] = []
    seen: set[str] = set()

    roots = [REPO_ROOT]
    try:
        roots.append(VIDEO_STORAGE_PATH)
    except Exception:
        pass

    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            rel = path.relative_to(root)
            if any(part in _SKIP_DIRS for part in rel.parts):
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                size_mb = round(path.stat().st_size / (1024 * 1024), 1)
            except OSError:
                size_mb = 0.0
            found.append({"name": path.name, "path": str(path), "size_mb": size_mb})

    found.sort(key=lambda v: v["name"].lower())
    _VIDEO_CACHE = found
    return [dict(v) for v in found]


def default_video_source() -> str:
    """The single unambiguous default video for the site.

    Priority: explicit ``VIDEO_SOURCE`` env, otherwise the project video if
    exactly one exists in the project folder, otherwise ``""``.
    """
    if DEFAULT_VIDEO_SOURCE:
        return DEFAULT_VIDEO_SOURCE
    videos = discover_videos()
    if len(videos) == 1:
        return videos[0]["path"]
    return ""


def clear_video_cache() -> None:
    global _VIDEO_CACHE
    _VIDEO_CACHE = None