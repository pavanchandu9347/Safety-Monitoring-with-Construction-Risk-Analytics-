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


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ── Authentication & session security ─────────────────────────────────────────
# In production JWT_SECRET_KEY MUST be set in the environment. A per-process
# random secret is only used so the platform boots without one; every restart
# then invalidates previously issued tokens (safe default, not a persistent
# secret). Tests override this variable explicitly.
JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "") or os.urandom(32).hex()
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = _env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 480)

# ── Demo manager bootstrap (placeholder credentials, never real secrets) ──────
# If unset a random password is generated and logged at startup so the seeded
# manager account is never created with a known, hardcoded password.
DEFAULT_MANAGER_EMAIL: str = os.environ.get("DEFAULT_MANAGER_EMAIL", "manager@buildsure.io").strip()
DEFAULT_MANAGER_PASSWORD: str = os.environ.get("DEFAULT_MANAGER_PASSWORD", "")

# ── Evidence-based risk-alert notification policy ─────────────────────────────
# A notification is only generated when the risk/safety scores reach these
# thresholds or a HIGH/CRITICAL condition is directly detected. Defaults mirror
# the project's 0-100 scoring bands: HIGH starts at 50, CRITICAL at 75. Raise
# the thresholds to 75 to restrict alerts to CRITICAL-only.
RISK_ALERT_THRESHOLD: float = _env_float("RISK_ALERT_THRESHOLD", 50.0)
SAFETY_ALERT_THRESHOLD: float = _env_float("SAFETY_ALERT_THRESHOLD", 50.0)
# Minimum severity that triggers an EXTERNAL channel (email). MEDIUM and below
# stay in-app only.
EMAIL_ALERT_MIN_LEVEL: str = os.environ.get("EMAIL_ALERT_MIN_LEVEL", "HIGH").upper()
# Cooldown (seconds) before a repeated notification for the same underlying
# condition is sent again. A severity escalation bypasses the cooldown.
NOTIFICATION_COOLDOWN_SECONDS: int = _env_int("NOTIFICATION_COOLDOWN_SECONDS", 300)

# ── External notification channel: SMTP email ─────────────────────────────────
# Only used when fully configured; otherwise in-app notifications still work and
# a clear message is logged. Credentials are never hardcoded.
SMTP_HOST: str = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT: int = _env_int("SMTP_PORT", 587)
SMTP_USERNAME: str = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")
NOTIFICATION_EMAIL_FROM: str = os.environ.get("NOTIFICATION_EMAIL_FROM", "").strip()


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

# The primary construction-site input video (base name, extension-insensitive).
# Contruction_vid is the single source of truth for the current data run.
PRIMARY_VIDEO_STEM: str = os.environ.get("PRIMARY_VIDEO_STEM", "contruction_vid").strip().lower()

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


def _stem_key(path: str) -> str:
    """Lowercased file stem (e.g. ``site3.mov`` → ``site3``)."""
    return Path(path).stem.lower()


def default_video_source() -> str:
    """The single unambiguous primary video for the site.

    Priority:
      1. explicit ``VIDEO_SOURCE`` env,
      2. the project's primary video (``PRIMARY_VIDEO_STEM``, default
         ``contruction_vid``) anywhere in the discovered set — root-level copies
         win over upload copies,
      3. the project video if exactly one exists,
      4. otherwise ``""``.
    """
    if DEFAULT_VIDEO_SOURCE:
        return DEFAULT_VIDEO_SOURCE

    videos = discover_videos()
    if not videos:
        return ""

    primary = [v for v in videos if _stem_key(v["path"]) == PRIMARY_VIDEO_STEM]
    if primary:
        # Prefer the repository-root copy (the canonical primary input) over
        # copies under the upload/storage folder.
        root_hits = [v for v in primary if Path(v["path"]).parent == REPO_ROOT]
        return (root_hits[0] if root_hits else primary[0])["path"]

    if len(videos) == 1:
        return videos[0]["path"]
    return ""


def clear_video_cache() -> None:
    global _VIDEO_CACHE
    _VIDEO_CACHE = None