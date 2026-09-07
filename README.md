# Agentic Construction Risk Intelligence Platform

An agentic AI platform for real-time construction site risk monitoring, hazard
detection, and explainable risk scoring.

> **Milestones 1–2 implemented** — *Site Risk Monitoring & Hazard Detection*
> and *Safety Agent / Worker Safety & PPE Compliance*
>
> **Milestones 3–4 planned** — *Compliance Agent, Insurance Agent, Reporting Agent*

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
agents. **The Site Risk Agent and Safety Agent are implemented.**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Construction Risk Intelligence Engine        │
├─────────────────────────────────────────────────────────────────────┤
│  Site Risk Agent  ◄── IMPLEMENTED (Milestone 1)                     │
│  Safety Agent     ◄── IMPLEMENTED (Milestone 2)                     │
│  Compliance Agent   (planned — Milestone 3)                         │
│  Insurance Agent    (planned — Milestone 3)                         │
│  Reporting Agent    (planned — Milestone 4)                         │
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

## 20. Database

SQLAlchemy ORM with SQLite (Milestone 1). Entities:

`Project` → `Site` → `Zone`, plus `MonitoringEvent`, `Hazard`,
`RiskAssessment`, `RiskFactor`, `Recommendation`, and `Equipment`.

The schema is designed so future agents (Milestones 2–4) can be added as new
tables / relationships without redesign.

## 21. Data Flow

```
Dataset / Video → Data Ingestion → Computer Vision → Object/Activity Detection
→ Monitoring Event → Environmental + Equipment Data → Site Risk Agent
→ Hazard Detection → Risk Assessment → Risk Score → Recommendations
→ Database → FastAPI → React Dashboard
```

## 22. Future Compatibility

Milestones 3–4 (Compliance, Insurance, Reporting agents) are **planned,
not implemented**. The `agents/` directory is structured to accommodate them
later, and the Site Risk / Safety agents have no dependency on future agents.

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
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Frontend
```bash
cd frontend
npm install
npm run dev -- --port 5179
```

### (Optional) Docker
```bash
docker-compose up --build
```

## 30. Running Instructions

1. Start the backend (port **8001**).
2. Start the frontend (port **5179**).
3. Open `http://localhost:5179` in a browser.
4. The backend auto-seeds the demo Riverside Tower site on first run.
5. Use the **Run Risk Analysis** / **Simulate Next Monitoring Tick** buttons to
   generate monitoring events and risk assessments.
6. Browse the Dashboard, Monitoring, Video, Hazards, and Risk Analysis pages.
7. View API docs at `http://localhost:8001/docs`.

> **Note on ports:** The default backend port is **8001** (port 8000 may be
> occupied by other processes on some machines). The frontend Vite proxy points
> to `http://localhost:8001`.

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

## 33. Current Limitations

- Milestones 1–2 implemented (Site Risk + Safety agents). Compliance / Insurance
  / Reporting agents are planned.
- Real PPE YOLO inference requires the trained weights at `ai/models/ppe.pt`
  (or `PPE_MODEL_PATH`). If absent, PPE analysis reports "model unavailable"
  and does not fabricate results; base COCO detection still works.
- Simulated environmental and equipment data (clearly labelled), not live
  sensors / CCTV. Simulated data is never used to replace real PPE inference on
  an uploaded image.
- Video processing uses frame sampling (not every frame) for performance.
- Detection models are pre-trained YOLO; PPE model is fine-tuned on the
  Construction-PPE dataset.

## 34. Future Milestones

- **Milestone 2 — Safety Intelligence & Worker Protection** (PPE detection,
  Safety Agent)
- **Milestone 3 — Compliance & Insurance** (Compliance Agent, Insurance Agent)
- **Milestone 4 — Reporting & Notifications** (Reporting Agent, Notification &
  Workflow module)

---

> **Engineering decisions** not specified by the PDF (e.g. risk-score weight
> distribution, threshold configuration, zone taxonomy, demo data structure) are
> documented here as design choices and kept configurable where appropriate.
