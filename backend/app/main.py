import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database.database import init_db
from app.api import (
    sites, monitoring, hazards, risk, dashboard, demo, safety, live, video,
    compliance, insurance, auth, notifications, reports,
)
from app.auth.deps import require_site_access

app = FastAPI(
    title="BuildSure",
    description=(
        "BuildSure — Construction Risk Intelligence Platform. "
        "Site Risk Monitoring & Hazard Detection (M1) · Safety Intelligence & "
        "Worker Protection (M2) · Compliance & Insurance Intelligence (M3) · "
        "Manager Auth & Intelligent Risk Alerts (M4) · Reporting Intelligence "
        "& Enterprise Deployment (M4)"
    ),
    version="4.0.0",
)

# CORS origins are configurable; the default keeps local development working.
# ``allow_credentials`` with a wildcard origin is invalid per the CORS spec, so
# credentials are only enabled when explicit origins are configured.
_cors_env = os.environ.get("CORS_ALLOW_ORIGINS", "").strip()
if _cors_env:
    _origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
    _allow_credentials = True
else:
    _origins = [
        "http://localhost:5173", "http://localhost:5179",
        "http://127.0.0.1:5173", "http://127.0.0.1:5179",
    ]
    _allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public: authentication + health. Everything else requires a valid manager
# token, and require_site_access additionally enforces per-site authorization
# whenever a site_id appears in the path or query string.
app.include_router(auth.router)
app.include_router(notifications.router)

_protected = [Depends(require_site_access)]
app.include_router(sites.router, prefix="/api", tags=["Sites"], dependencies=_protected)
app.include_router(monitoring.router, prefix="/api", tags=["Monitoring"], dependencies=_protected)
app.include_router(hazards.router, prefix="/api", tags=["Hazards"], dependencies=_protected)
app.include_router(risk.router, prefix="/api", tags=["Risk Assessment"], dependencies=_protected)
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"], dependencies=_protected)
app.include_router(demo.router, prefix="/api", tags=["Demo"], dependencies=_protected)
app.include_router(safety.router, prefix="/api", tags=["Safety Intelligence"], dependencies=_protected)
app.include_router(compliance.router, prefix="/api", tags=["Compliance Intelligence"], dependencies=_protected)
app.include_router(insurance.router, prefix="/api", tags=["Insurance Intelligence"], dependencies=_protected)
app.include_router(reports.router, prefix="/api", tags=["Reporting Intelligence"], dependencies=_protected)
# live.router carries an authenticated WebSocket + token-backed MJPEG stream;
# its HTTP routes protect themselves individually.
app.include_router(live.router, prefix="/api", tags=["Live Analysis"])
app.include_router(video.router, prefix="/api", tags=["Video Analysis"], dependencies=_protected)


@app.on_event("startup")
def startup():
    from app.logging_config import setup_logging
    setup_logging()
    init_db()
    from app.services.seed import seed_demo_data
    seed_demo_data()


@app.on_event("shutdown")
def shutdown():
    from app.live.pipeline import manager
    manager.shutdown()


@app.get("/api/health")
def health_check():
    """Readiness probe: app is up and the configured database is reachable.

    Cheap single ``SELECT 1`` per probe — suitable as a Docker healthcheck.
    """
    try:
        from sqlalchemy import text
        from app.database.database import engine as _engine

        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001 - health probe must never 500
        db_status = "unavailable"

    if db_status != "ok":
        from fastapi import Response

        return Response(
            status_code=503,
            content='{"status":"degraded","db":"unavailable"}',
            media_type="application/json",
        )

    return {"status": "ok", "milestone": 4, "db": db_status}
