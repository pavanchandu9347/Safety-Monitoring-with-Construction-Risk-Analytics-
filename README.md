# BuildSure — Construction Risk Intelligence Platform

An agentic AI platform for real-time construction site risk monitoring, hazard
detection, and explainable risk scoring.

> **Milestones 1–4 implemented** — *Site Risk Monitoring & Hazard Detection*,
> *Safety Agent / Worker Safety & PPE Compliance*,
> *Compliance Agent + Insurance Agent* (regulatory validation, inspection status,
> insurance risk exposure & claim documentation), and
> **Manager Authentication + Smart Risk Alerts** (JWT-based site authorization,
> evidence-based notification pipeline, bell UI with WebSocket push).
>
> **Milestone 5 planned** — *Reporting Agent*

---

> **Evidence policy:** agents only render verdicts from **real verified evidence**.
> Missing documentation / video evidence yields `NOT_VERIFIED` /
> `NOT_AVAILABLE` / `INSUFFICIENT_EVIDENCE` — no data is ever fabricated.

---

## 1. Problem Statement

Construction sites are hazardous environments with heavy equipment, workers,
changing environmental conditions, and demanding schedules. Safety managers
must monitor multiple zones, detect unsafe conditions, and act quickly. Without
an integrated, explainable monitoring system, hazards go unnoticed until an
incident occurs.

## 2. Project Objective

Deliver a working **Site Risk Intelligence prototype** that ingests construction
monitoring data (imagery + environmental + equipment telemetry), detects
hazards, computes an **explainable site risk score (0–100)**, and surfaces
actionable recommendations through a unique construction operations dashboard.

## 3. Agentic AI Architecture

The full platform (per the project requirements) is composed of cooperating
agents. **The Site Risk Agent, Safety Agent, Compliance Agent, and Insurance
Agent are implemented.**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Construction Risk Intelligence Engine        │
├─────────────────────────────────────────────────────────────────────┤
│  Site Risk Agent  ◄── IMPLEMENTED (Milestone 1)                     │
│  Safety Agent     ◄── IMPLEMENTED (Milestone 2)                     │
│  Compliance Agent ◄── IMPLEMENTED (Milestone 3)                     │
│  Insurance Agent  ◄── IMPLEMENTED (Milestone 3)                     │
│  Manager Auth + Smart Risk Alerts ◄── IMPLEMENTED (Milestone 4)     │
│  Reporting Agent    (planned — Milestone 5)                         │
└─────────────────────────────────────────────────────────────────────┘
```

The **Site Risk Agent** is a modular component (not a single giant function):

```
backend/app/agents/site_risk_agent/
├── agent.py                    # Orchestrator
├── hazard_detector.py          # Data-derived hazard detection
├── environmental_analyzer.py   # Environmental risk score
├── equipment_analyzer.py       # Equipment risk score
├── site_condition_analyzer.py  # Site-condition risk score
├── risk_scorer.py              # Weighted overall risk score
└── recommendation_engine.py    # Actionable recommendations
```

The **Safety Agent** monitors worker safety and PPE compliance (Milestone 2):

```
backend/app/agents/safety_agent/
├── agent.py                        # Orchestrator (overall safety score 0-100)
├── worker_safety_monitor.py        # Worker/equipment density risk
├── unsafe_behavior_detector.py     # Swing-radius, overexertion detection
├── accident_zone_analyzer.py       # High-risk zone ranking
├── safety_hazard_detector.py       # Safety hazard identification
├── safety_recommendation_engine.py # Corrective recommendations
└── ppe_compliance.py               # PPE compliance scoring
```

The **Compliance Agent** validates regulatory standards & inspections using only
verified evidence (Milestone 3):

```
backend/app/agents/compliance_agent/
├── agent.py                    # Orchestrator (inspection tracker → validate → score)
├── standards_monitor.py        # Requirement ↔ live detection mapping
├── regulatory_validator.py     # Evidence-only verdicts (NOT_VERIFIED when absent)
├── policy_violation_detector.py# Policy violations from verified safety data
├── inspection_tracker.py       # OVERDUE / DUE inspection status (datetime-aware)
├── compliance_scorer.py        # Weighted score over VERIFIED verdicts only
└── recommendation_engine.py    # Evidence-referenced corrective actions
```

The **Insurance Agent** derives incident risk, exposure, and claim documentation
(Milestone 3):

```
backend/app/agents/insurance_agent/
├── agent.py                    # Orchestrator (incidents → exposure → claims)
├── incident_severity.py        # Multi-factor severity classification
├── exposure_analyzer.py        # Worker / equipment / incident exposure tiers
├── claim_risk_analyzer.py      # Explainable claim risk (ML-free factors)
├── insurance_scorer.py         # Overall insurance risk score
├── claim_documentation.py      # Claim docs only for verified incidents
└── recommendation_engine.py    # Claim-response recommendations
```

Custom **PPE detection engine** (Milestone 2):

```
ai/computer_vision/ppe_detector.py  # Real YOLO PPE detector (Construction-PPE classes)
                                    # Loaded once & cached; weights: ai/models/ppe.pt (PPE_MODEL_PATH)
                                    # NO simulated fallback — reports clearly if unavailable
```

The PPE detector performs **real, image-dependent YOLO inference** on each
uploaded image. Class labels come from the model's actual class table. Results
depend on the actual uploaded image (different images → different detections).
If the weights file is missing, the backend returns a clear "PPE model
unavailable" response (no fabricated detections) and the frontend shows it.

The workflow for an uploaded image:

```
User uploads construction image
        ↓
FastAPI receives actual image
        ↓
YOLO (base COCO) detection → real person/vehicle boxes
        ↓
PPE YOLO model inference → real PPE class boxes + confidence
        ↓
PPE compliance (bounding-box association: worker ↔ worn PPE / missing-* classes)
        ↓
Safety Agent (PPE 40% / worker 40% / accident 20%)
        ↓
Violations / alerts / safety score
        ↓
Frontend (image + bounding boxes, compliance, recommendations)
```

## 4. Milestone 1 Scope

| Deliverable | Status |
|---|---|
| Site Risk Agent | ✅ Implemented |
| Integrate site monitoring data | ✅ (dataset + simulated) |
| Hazard detection workflows | ✅ Implemented |
| Site risk scoring | ✅ Implemented (explainable, 0–100) |
| Risk monitoring dashboard | ✅ Implemented |

**Week 2 evaluation criteria:**
- ✅ Site risk monitoring operational
- ✅ Hazard detection functioning
- ✅ Site risk dashboard available

## 5. Milestone 2 Scope — Safety Agent

| Deliverable | Status |
|---|---|
| Safety Agent (worker safety orchestration) | ✅ Implemented |
| Custom PPE detection (helmet / vest / gloves / goggles) | ✅ Implemented (real YOLO inference) |
| Worker safety monitoring (density / swing-radius) | ✅ Implemented |
| Accident-prone zone analysis | ✅ Implemented |
| Safety hazard + recommendation engine | ✅ Implemented |
| Safety alerts & violations | ✅ Implemented |
| Safety analytics dashboard | ✅ Implemented |
| Explainable overall safety score (0–100) | ✅ Implemented |

**Safety scoring (weighted):** PPE compliance 40% / worker monitoring 40% /
accident zones 20% → overall safety level (LOW < 25, MEDIUM < 50, HIGH < 75,
CRITICAL ≥ 75).

**New API endpoints (Milestone 2):**
- `POST /sites/{id}/safety/analyze` — run the full Safety Agent for a site
- `GET /sites/{id}/safety/dashboard` — safety analytics overview
- `GET /sites/{id}/workers` — worker PPE register
- `GET /sites/{id}/safety/violations` — list violations (`PATCH .../status` to update)
- `GET /sites/{id}/safety/alerts` — safety alert feed

## 5b. Milestone 3 Scope — Compliance & Insurance Intelligence

Both agents run **inside the same unified analysis pipeline** as the Safety
Agent (`run_analysis` in `backend/app/services/analysis_pipeline.py`): one video
input → one shared `analysis_id` → Safety → Compliance → Insurance.

| Deliverable | Status |
|---|---|
| Compliance Agent (regulatory validation) | ✅ Implemented |
| Reference compliance requirements / baselines | ✅ 15 requirements · 8 categories |
| Inspection tracker (DUE / OVERDUE, never fabricated) | ✅ Implemented |
| Evidence-only verdicts (`NOT_VERIFIED` when unavailable) | ✅ Implemented |
| Weighted compliance score over verified verdicts | ✅ Implemented |
| Policy-violation identification | ✅ Real `SafetyViolation` rows |
| Insurance Agent (incident & exposure intelligence) | ✅ Implemented |
| Incident derivation (HIGH/CRITICAL hazards + CRITICAL alerts) | ✅ Implemented |
| Multi-factor incident severity | ✅ Implemented |
| Claim documentation (verified incidents only) | ✅ Implemented |
| Compliance + Insurance dashboards (frontend) | ✅ Implemented |

**Shared-analysis contract:** all Milestone‑3 rows persist with the same
`analysis_id` as the Safety Assessment, so every verdict is traceable to the same
video frames.

> **Engineering decision:** because construction compliance / insurance
> documentation (certificates, permits, completed inspections) is not observable
> from video, the agents mark such items `NOT_VERIFIED` (reason: *"Required
> documentation/evidence unavailable"*) and compute the compliance score over the
> **verified** subset only — the platform never fabricates evidence of
> compliance.

**New API endpoints (Milestone 3):**
- Compliance: `POST /sites/{id}/compliance/analyze`, `GET .../compliance/dashboard`,
  `GET .../compliance/findings`, `GET .../compliance/requirements`,
  `GET .../compliance/inspections`, `GET .../compliance/assessment`
- Insurance: `POST /sites/{id}/insurance/analyze`, `GET .../insurance/dashboard`,
  `GET .../insurance/incidents`, `GET .../insurance/claims`,
  `GET .../insurance/assessment`

## 6. Input / Data Strategy

There is **no physical construction site** available. Therefore the system is
built around:

1. **Construction dataset / pre-recorded video** — via a modular computer vision
   pipeline (images, videos, extracted frames).
2. **Simulated environmental monitoring** — deterministic, clearly labelled.
3. **Simulated equipment telemetry** — deterministic, clearly labelled.

Everything is explicitly labelled **Demo / Simulated Site Monitoring** in the UI
and code. The architecture is designed so real CCTV, IoT sensors, and equipment
telemetry can be connected later **without redesigning the Site Risk Agent**.

## 7. Dataset / Video Processing

The computer vision pipeline is modular:

```
backend/
  Video → Frame Extraction → Object Detection → Monitoring Event → Site Risk Agent
  Image → Object Detection  → Construction Objects → Monitoring Event → Site Risk Agent
```

Implemented as:

```
ai/
├── computer_vision/
│   ├── detector.py          # YOLO object detection
│   └── frame_extractor.py   # Video frame sampling
└── preprocessing/
    └── image_utils.py       # Image utilities
```

- Uses a **YOLO model** (yolov8n) with COCO classes appropriate for
  construction (person/worker, truck, vehicle, etc.).
- Video uses **controlled frame sampling** (1 frame every N frames) to keep
  processing efficient.
- The input dataset (e.g. **CSOD-24** construction-site dataset) is **not
  bundled** — see `data/README.md` for placement instructions. The pipeline
  handles missing inputs gracefully.

### What is detected (Milestone 1)
- Workers / persons
- Construction vehicles (trucks, excavators etc.)
- Equipment operating areas

> **PPE / helmet / vest detection is implemented in *Milestone 2 (Safety Agent)***
> via `ai/computer_vision/ppe_detector.py`. Milestone 1 focuses on worker/vehicle
> detection; the detection architecture is shared so both run on the same frames.

## 8. Site Monitoring Event Model

Computer-vision detections and simulated monitoring are converted into
structured **site monitoring events** (Pydantic models):

```json
{
  "timestamp": "...",
  "site_id": "site_riverside_main",
  "zone": "Excavation Zone A",
  "event_type": "construction_activity",
  "detected_objects": [
    {"label": "person", "confidence": 0.89, "count": 3, "class_id": 0},
    {"label": "excavator", "confidence": 0.91, "count": 1, "class_id": 7}
  ],
  "equipment_activity": {"Excavator-01": {"status": "active", "activity": "excavation"}},
  "environmental_conditions": {"weather": "Rainy", "visibility": "Poor", "...": "..."},
  "site_conditions": {"ground_condition": "Wet", "lighting_condition": "Adequate"}
}
```

## 9. Site Risk Agent

Responsibilities (as defined by the requirements PDF):
- Monitor construction site activities
- Detect unsafe site conditions
- Assess environmental risks
- Identify equipment-related hazards
- Generate site risk scores

Implemented as a modular backend component in `backend/app/agents/site_risk_agent/`.

## 10. Hazard Detection

Hazards are **derived from actual data** — never random. Sources include:
- Computer vision detections (e.g. heavy equipment near workers)
- Environmental monitoring (e.g. poor visibility during active operation)
- Equipment monitoring (e.g. overdue maintenance)
- Site-condition data (e.g. wet ground + active construction)

Each hazard carries:

| Field | Example |
|---|---|
| Hazard ID | `haz_...` |
| Type | `equipment_proximity` |
| Description | "Heavy equipment operating near workers" |
| Severity | LOW / MEDIUM / HIGH / CRITICAL |
| Risk contribution | `+30` |
| Zone | `zone_a` |
| Timestamp | `...` |
| **Evidence / source** | `"Excavator detected with 3 workers within monitored zone."` |
| Recommended mitigation | "Restrict worker access around the active equipment operating zone" |
| Status | detected / investigating / mitigated / resolved |

## 11. Evidence

**Every hazard includes an evidence/source field** so risk analysis is
explainable. The dashboard shows **why** a hazard was detected.

```
Source: Computer Vision
Evidence: "Excavator detected with 3 workers within monitored zone."
```

## 12. Risk Scoring Methodology

An explainable **Site Risk Score from 0–100** is computed from weighted,
data-derived components:

```
Environmental Risk (25%)
+ Equipment Risk (30%)
+ Site Condition Risk (20%)
+ Activity Risk (25%)
→ Overall Site Risk Score (0–100)
```

### Classification (configurable)
| Score | Level |
|---|---|
| 0–24 | LOW |
| 25–49 | MEDIUM |
| 50–74 | HIGH |
| 75–100 | CRITICAL |

> **Engineering decision:** The weight distribution (0.25 / 0.30 / 0.20 / 0.25)
> is a sensible design choice made for this implementation. It is **not** taken
> from the PDF, which does not specify an exact formula. It is configurable in
> `RiskScorer`.

The score is **deterministic and explainable** — every point is traceable to a
contributing factor with evidence. No random numbers.

## 13. Risk Trend

Historical risk assessments are stored, enabling the dashboard to show whether
risk is **increasing, stable, or decreasing** over time (e.g.
`10:00 → 42, 10:05 → 48, 10:10 → 57`).

## 14. Recommendation Engine

Recommendations are generated from detected hazards / risk factors — not generic
text. Example:

- **Hazard:** Heavy equipment operating near workers
- **Recommendation:** "Enforce equipment exclusion zones — restrict worker access
  around the active operating zone and verify separation controls."

## 14–16. Frontend — Unique Design

The frontend uses the **"Construction Site Risk Operations Center"** design
language — combining construction operations, safety intelligence, real-time
monitoring, and AI risk analysis. It is **not** a generic dashboard.

Components include:
- Overall risk score ring with live risk level
- Risk component breakdown (environmental / equipment / site condition / activity)
- A **Virtual Construction Site map** with clickable zones
- Live monitoring feed
- Equipment telemetry panel

## 15. Monitoring Feed

A live-looking stream fed by **real backend data** (not fabricated frontend
animations), showing environmental updates, equipment detections, risk events,
and recommendations.

## 16. Dataset / Video Viewer

A dedicated page where the user can upload a construction image, run computer
vision processing, and see detected objects, the generated monitoring event,
and resulting risk analysis.

## 17. Hazards Page

A functional page listing hazards with **search** and filters by **severity**,
**type**, and **zone**, showing evidence, recommendation, timestamp, and status
(detected / investigating / mitigated / resolved) — all backed by APIs.

## 18. Risk Analysis Page

Shows the overall risk plus each component score and explains **why** the score
exists, e.g.:

```
Overall Risk: 78 — CRITICAL
Equipment Risk: 82 → Heavy equipment active
Environmental Risk: 76 → Poor visibility, High wind
Site Condition Risk: 70 → Wet ground
```

## 19. Backend API

FastAPI with Pydantic validation, HTTP status codes, error handling, service
layers, and **Swagger/OpenAPI** at `/docs`.

| Method | Route |
|---|---|
| GET | `/api/health` |
| GET | `/api/projects` |
| GET | `/api/sites` |
| GET | `/api/sites/{site_id}` |
| POST | `/api/sites` |
| GET | `/api/sites/{site_id}/zones` |
| GET | `/api/sites/{site_id}/monitoring` |
| POST | `/api/monitoring/analyze` |
| POST | `/api/monitoring/simulate` |
| POST | `/api/monitoring/process-image` |
| GET | `/api/sites/{site_id}/hazards` |
| GET | `/api/hazards/{hazard_id}` |
| PATCH | `/api/hazards/{hazard_id}/status` |
| GET | `/api/sites/{site_id}/risk` |
| POST | `/api/sites/{site_id}/risk/analyze` |
| GET | `/api/sites/{site_id}/risk/history` |
| GET | `/api/sites/{site_id}/recommendations` |
| GET | `/api/sites/{site_id}/dashboard` |
| POST | `/api/demo/generate` |
| GET | `/api/demo/scenario` |
| GET | `/api/demo/environmental` |
| GET | `/api/demo/equipment` |
| POST | `/api/sites/{id}/compliance/analyze` |
| GET | `/api/sites/{id}/compliance/dashboard` |
| GET | `/api/sites/{id}/compliance/findings` |
| GET | `/api/sites/{id}/compliance/requirements` |
| GET | `/api/sites/{id}/compliance/inspections` |
| GET | `/api/sites/{id}/compliance/assessment` |
| POST | `/api/sites/{id}/insurance/analyze` |
| GET | `/api/sites/{id}/insurance/dashboard` |
| GET | `/api/sites/{id}/insurance/incidents` |
| GET | `/api/sites/{id}/insurance/claims` |
| GET | `/api/sites/{id}/insurance/assessment` |
| POST | `/api/auth/login` |
| GET | `/api/auth/me` |
| POST | `/api/auth/logout` |
| GET | `/api/notifications` |
| GET | `/api/notifications/unread-count` |
| PATCH | `/api/notifications/{id}/read` |
| PATCH | `/api/notifications/read-all` |
| DELETE | `/api/notifications/{id}` |

## 20. Database

SQLAlchemy ORM with SQLite. Entities:

`Project` → `Site` → `Zone`, plus `MonitoringEvent`, `Hazard`,
`RiskAssessment`, `RiskFactor`, `Recommendation`, `Equipment`
(Milestone 1) and `SafetyViolation`, `SafetyAlert`, `WorkerRecord`,
`SafetyAssessment` (Milestone 2). Milestone 3 adds `ComplianceRequirement`,
`ComplianceFinding`, `InspectionRecord`, `ComplianceAssessment`,
`InsuranceAssessment`, `InsuranceIncident`, and `ClaimRecord` — all share
`site_id` / `analysis_id` so every agent verdict is traceable to the same
video analysis. Milestone 4 adds `Manager` (name, email, password hash,
role, site_id, token_version) and `Notification` (type, severity, title,
message, source, evidence JSON, dedup_key, status, read_at, site_id,
manager_id).

## 21. Data Flow

```
Dataset / Video → Data Ingestion → Computer Vision → Object/Activity Detection
→ Monitoring Event → Environmental + Equipment Data → Site Risk Agent
→ Hazard Detection → Risk Assessment → Risk Score → Recommendations
→ Database → FastAPI → React Dashboard
```

## 22. Milestone 4 — Manager Auth & Smart Risk Alerts

Milestone 4 delivers **manager authentication** and an **evidence-based risk
alert pipeline** delivered in-app via WebSocket push.

### 22.1 Manager Authentication

- `Manager` records store role-scoped identities (e.g. site manager) linked to
  a single `site_id`. Passwords are hashed with stdlib `hashlib.scrypt`
  (format `scrypt$N$R$P$salt$digest`).
- Login (`POST /api/auth/login`) issues an HS256 JWT (`PyJWT`) carrying the
  manager id, role, site_id, and a `ver` claim bound to `token_version`. Logout
  bumps `token_version`, invalidating every outstanding token server-side.
- `require_site_access` enforces per-site authorization on every data route:
  a manager can only read/write their own site (admins bypass). Media endpoints
  (`?token=` query fallback) and the authenticated WebSocket (`live/video`,
  `ws_live`) are covered too.

### 22.2 Smart Risk Alerts

- After every analysis, `evaluate_analysis()` turns **real persisted rows**
  (SafetyAlert, SafetyViolation, Hazard, InsuranceIncident) plus the risk/safety
  summaries into a severity-ranked notification. No fabricated data — evidence
  is attached to every alert and "insufficient evidence" is reported explicitly.
- **Policy:** severity is derived from the real level + score cross-check
  (score ≥ 75 → CRITICAL, ≥ 50 → HIGH). Alerts below `RISK_ALERT_THRESHOLD`
  are downgraded to MEDIUM (in-app only). Strongest condition wins via a
  priority tuple (severity, score, specificity).
- **Dedup / cooldown:** repeated occurrences of the same condition
  (`dedup_key`) are suppressed within `NOTIFICATION_COOLDOWN_SECONDS` unless the
  severity escalates (e.g. HIGH → CRITICAL bypasses the cooldown).
- **Delivery:** notifications are pushed over the WebSocket hub in real time and
  stored so the bell/badge and API inbox stay consistent. Severity ≥
  `EMAIL_ALERT_MIN_LEVEL` messages are emailed when SMTP is configured; if
  email/SMTP is unavailable the alert remains fully in-app.

### 22.3 Live Site Alert

The dashboard surfaces the strongest live alert (HTTP + WebSocket) as an
"Active Risk Alert" banner with severity color, contributing factors, and risk
score — the same evidence the notification was built from.

### 22.4 Frontend

Login page (`/login`), protected layout wrapper, axios Bearer interceptor with
401 → redirect, notification bell with unread badge + dropdown (severity
colors, time-ago, evidence count, mark-read / mark-all, navigate to source),
and per-manager site scoping throughout.

## 23. Future Compatibility

The Reporting Agent (Milestone 5) is **planned, not implemented**. The `agents/`
directory is structured so future agents can be added without redesign, no
existing agent depends on it, and the Milestone 4 notification pipeline is
designed to consume any future agent's verdicts.

## 25. PPE Detection — Real YOLO Inference

PPE detection (Milestone 2) is implemented as a **real YOLO inference** engine
in `ai/computer_vision/ppe_detector.py`, trained on the Construction-PPE
dataset (11 classes: helmet, gloves, vest, boots, goggles, no_helmet,
no_gloves, no_boots, no_goggle, Person, none). See the "PPE detection engine"
section under Agentic AI Architecture for the full image-analysis flow.

## 26. Demo Mode

A clearly defined **Demo Monitoring Mode** provides immediate, realistic
operational output:
- Construction dataset / demo image
- Simulated environmental data
- Simulated equipment telemetry
- Monitoring events
- Hazard analysis
- Risk scoring
- Recommendations

Launch it and click **"Run Risk Analysis"** / **"Simulate Next Monitoring Tick"**
to see the system operate.

## 27. No Random Demo Values

Every risk score has identifiable contributing factors; every hazard has
evidence; every recommendation maps to a hazard / risk factor. The system is
deterministic and explainable.

## 28. Project Structure

```
AgenticConstructionRiskIntelligence/
├── frontend/               # React + Vite + Tailwind
│   └── src/{components,pages,layouts,services,hooks,utils}
├── backend/
│   └── app/
│       ├── api/            # FastAPI routes
│       ├── agents/site_risk_agent/
│       ├── models/         # SQLAlchemy models
│       ├── schemas/        # Pydantic schemas
│       ├── services/       # Seed + simulated data
│       ├── database/
│       └── main.py
├── ai/
│   ├── computer_vision/    # detector, frame extraction
│   └── preprocessing/
├── data/{raw,processed,demo}
├── tests/
├── docs/
├── .env.example
├── .gitignore
├── README.md
└── docker-compose.yml
```

## 29. Setup Instructions

Requires Python 3.10+ and Node 18+.

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit with real values
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Set a persistent **JWT secret** (32+ random bytes) in `backend/.env`
(`JWT_SECRET_KEY`) and optionally a known demo login via
`DEFAULT_MANAGER_EMAIL` / `DEFAULT_MANAGER_PASSWORD`. If the password is left
empty a cryptographically random one is generated and logged once at startup.
`APP_ENV=production` fails fast at startup when `JWT_SECRET_KEY` is missing.

### Frontend
```bash
cd frontend
npm install
npm run dev -- --port 5179
```

### (Optional) Docker — production topology
```bash
cp .env.example .env        # set JWT_SECRET_KEY + POSTGRES_PASSWORD
docker compose up --build -d
```
nginx serves the compiled frontend and proxies `/api` (HTTP + WebSocket) to the
FastAPI backend (Gunicorn/Uvicorn) backed by PostgreSQL. Health probes run
against `/api/health`. See the production-deployment section below.

## 30. Running Instructions

1. Start the backend (port **8000**).
2. Start the frontend (port **5179**).
3. Open `http://localhost:5179` in a browser — you'll land on the **login page**.
4. Log in with the seeded manager credentials (see `DEFAULT_MANAGER_*` above).
5. The backend auto-seeds the demo Riverside Tower site and demo manager on
   first run (skipped when `DEMO_MODE=false`).
6. Use the **Analyze Video** / **Simulate Next Monitoring Tick** buttons to run
   the real video pipeline (queued → processing → completed) and generate risk
   assessments — high-severity findings surface immediately in the
   **notification bell**.
7. Browse the Dashboard, Monitoring, Video, Hazards, and Risk Analysis pages.
8. View API docs at `http://localhost:8000/docs`.

> **Note on ports:** The whole stack uses a single backend port, **8000** (Vite's
> dev proxy and the nginx container both forward `/api` to `localhost:8000`).
> The frontend dev server runs on **5179**.

## 31. Demo Instructions

- **Dashboard** — shows the live overall risk score, risk components, virtual
  site zones, active hazards, monitoring feed, and equipment telemetry.
- **Monitoring** — click **"Simulate Next Monitoring Tick"** to ingest simulated
  environmental + equipment data and stream monitoring events.
- **Dataset / Video** — upload a construction image to run YOLO object detection
  and generate a monitoring event from detections.
- **Hazards** — filter, inspect evidence, and update status.
- **Risk Analysis** — view the explainable score breakdown and recommendations.

## 32. Dataset Instructions

See `data/README.md`. Recommended: **CSOD-24** construction-site dataset
(excavators, dump trucks, workers). Place videos/images in `data/raw/`. If no
dataset is available, the demo image in `data/demo/` and uploads are used.

## 33. Production Deployment & HTTPS

### Architecture
- **Frontend** — production build (Vite) served by nginx (`frontend/Dockerfile`,
  `frontend/nginx.conf`). The browser talks only to nginx on `/` and `/api/`.
- **Backend** — FastAPI served by **Gunicorn + UvicornWorker** on `:8000`
  (`backend/Dockerfile`). Runs `alembic upgrade head` before starting; the
  DB-layer `create_all` remains as a safety net. One worker is the safe default
  (in-process job queue + rate limiter + WebSocket fan-out stay coherent);
  scale horizontally behind the proxy if needed.
- **Database** — PostgreSQL 16 volume (`postgres_data`), healthchecked with
  `pg_isready`; backend depends on it via `service_healthy`.

### Environment variables (see `.env.example` at the repo root and
`backend/.env.example`)
- `JWT_SECRET_KEY` — required in production; persistent (tokens survive
  restarts). `APP_ENV=production` refuses to start without it.
- `POSTGRES_PASSWORD` / `POSTGRES_USER` / `POSTGRES_DB` — compose secrets.
- `DEMO_MODE` — `false` disables the built-in manager account AND compiles the
  demo-credenths quick-access card out of the login page.
- `MAX_UPLOAD_SIZE_MB` — upload cap (HTTP 413 above it); files stream to disk.
- `CORS_ALLOW_ORIGINS` — only needed when the API is served cross-origin.

### Health checks
- `/api/health` runs a `SELECT 1` against the database and returns
  `{"status":"ok","milestone":4,"db":"ok"}` (`503` degraded when DB is down).
- Every container ships a `HEALTHCHECK` that probes this endpoint through its
  own network path (nginx → backend), so an unhealthy backend unblocks the
  frontend wait automatically.

### HTTPS / TLS readiness
- **WebSockets** are negotiated from the configured API base: the frontend picks
  `wss://` automatically when the page is served over `https:` (see
  `api.js` → `liveWsUrl`), and nginx forwards the `Upgrade` header for
  `/api/ws/`. No schema hard-coding.
- Terminate TLS at the reverse proxy in front of nginx (recommended) — e.g.
  Caddy, Traefik, or `docker compose` + a TLS-terminating proxy:
  - Caddy: `https://app.example.com { reverse_proxy frontend:80 }` (auto-HTTPS).
  - Traefik/nginx: load the Let's Encrypt cert secrets into the proxy; the
    container's `:80` port stays plain HTTP behind it.
  - Set `DEPLOYMENT_URL=https://app.example.com` so notification links are
    HTTPS. `CORS_ALLOW_ORIGINS` only matters for cross-origin setups.
- The MJPEG live-view stream and the API share the same origin via nginx, so no
  TLS-related mixed-content warnings occur.

## 34. Current Limitations

- Milestones 1–4 implemented (Site Risk, Safety, Compliance, Insurance agents,
  Manager Auth & Smart Risk Alerts, Reporting Intelligence, PostgreSQL prod
  storage, Docker deployment). PDF/PPTX export of reports is a future addition.
- Real PPE YOLO inference requires the trained weights at `ai/models/ppe.pt`
  (or `PPE_MODEL_PATH`). If absent, PPE analysis reports "model unavailable"
  and does not fabricate results; base COCO detection still works.
- Compliance / insurance documentation (certificates, permits, completed
  inspection records) is not observable from video. Such items are reported
  `NOT_VERIFIED` with an explicit "evidence unavailable" reason rather than
  fabricated — scores are computed over the verified subset only.
- Simulated environmental and equipment data (clearly labelled), not live
  sensors / CCTV. Simulated data is never used to replace real PPE inference on
  an uploaded image.
- Video processing uses frame sampling (not every frame) for performance.
- Detection models are pre-trained YOLO; PPE model is fine-tuned on the
  Construction-PPE dataset.

## 35. Future Milestones

- **Milestone 5 — Reporting Agent** (PDF/PPTX report generation, compliance
  reports, analytics dashboard)
- Enhanced notification routing (e.g. Slack / per-role escalation), more
  granular targeting, and multi-tenant manager roles.

---

> **Engineering decisions** not specified by the PDF (e.g. risk-score weight
> distribution, threshold configuration, zone taxonomy, demo data structure) are
> documented here as design choices and kept configurable where appropriate.
