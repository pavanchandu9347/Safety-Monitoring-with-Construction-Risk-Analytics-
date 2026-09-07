from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database.database import init_db
from app.api import sites, monitoring, hazards, risk, dashboard, demo, safety, live

app = FastAPI(
    title="Agentic Construction Risk Intelligence Platform",
    description="Site Risk Monitoring & Hazard Detection (M1) · Safety Intelligence & Worker Protection (M2)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sites.router, prefix="/api", tags=["Sites"])
app.include_router(monitoring.router, prefix="/api", tags=["Monitoring"])
app.include_router(hazards.router, prefix="/api", tags=["Hazards"])
app.include_router(risk.router, prefix="/api", tags=["Risk Assessment"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(demo.router, prefix="/api", tags=["Demo"])
app.include_router(safety.router, prefix="/api", tags=["Safety Intelligence"])
app.include_router(live.router, prefix="/api", tags=["Live Analysis"])


@app.on_event("startup")
def startup():
    init_db()
    from app.services.seed import seed_demo_data
    seed_demo_data()


@app.on_event("shutdown")
def shutdown():
    from app.live.pipeline import manager
    manager.shutdown()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "milestone": 2}
