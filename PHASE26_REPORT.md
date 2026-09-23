# Phase 26 — Production-Hardening Verification Report

Status: **COMPLETE**
Date: 2026-09-22

## Scope

Production hardening of BuildSure (M1–M4) across phases: single backend port, health/degradation, secret
handling, login rate limiting, N+1 query elimination, production Docker topology (Nginx + Gunicorn/Uvicorn +
PostgreSQL), upload limits/whitelist, background video analysis with a queued API contract, demo gating,
frontend/backend automated tests, documentation, and a production-like end-to-end acceptance run.

Note: Docker was previously unavailable on this machine; it is now installed and the production stack has been
**built, started and acceptance-tested here** (evidence below).

## Verification Evidence

### 1. Import / config smoke check (backend venv, not the broken root venv)
```
IMPORTS OK | PORT 8000 | DEMO True | UPLOAD_MB 500
```

### 2. Backend test suite on PostgreSQL — 124/124 passed
```
$ DATABASE_URL="postgresql+psycopg2://buildsure@localhost:5433/buildsure" \
  TESTING=1 backend/venv/bin/python -m pytest tests/ -q
124 passed
```
(only deprecation warnings from `on_event`/`utcnow`/TestClient — pre-existing, non-fatal)

### 3. Frontend test suite — 11/11 passed
`npm test` (vitest + Testing-Library): Login (5), Dashboard (2), ReportSections (4).
`npm run lint`: 0 errors (32 pre-existing dep warnings). `npm run build`: green.

### 4. PostgreSQL production-mode acceptance (`gunicorn` + `uvicorn.workers.UvicornWorker`, PG, fixed JWT key, porta 8010 for local test)
```
GET /api/health                          -> {"status":"ok","milestone":4,"db":"ok"} [200]
GET /api/health (PG stopped, then 503)   -> {"status":"degraded","db":"unavailable"} [503]
GET /api/health (PG restored)            -> {"status":"ok","milestone":4,"db":"ok"} [200]
POST /auth/login good                    -> access_token
POST /auth/login x6 wrong                -> 401,401,401,401,401,429   (rate limit trip at 6)
POST /video/analyze (.txt)               -> [400]  (extension whitelist)
POST /video/analyze (51 MB file, cap 50) -> [413] "Upload of 51.0 MB exceeds the 50 MB limit."
GET  /auth/me (token, before restart)    -> [200]
   (backend fully restarted with the SAME JWT_SECRET_KEY)
GET  /auth/me (same token, after restart)-> [200]  (persistent-secret session survives restart)
APP_ENV=production, no JWT_SECRET_KEY    -> RuntimeError (fail fast) confirmed
```

### 5. Browser E2E (Playwright + Chromium against `vite preview`, absolute `VITE_API_URL=http://localhost:8010/api`)
```
PASS: login page renders brand
PASS: demo quick-access card visible
PASS: login + dashboard renders with real data
PASS: video analysis completes and output renders     (queued -> polling -> completed)
PASS: executive report renders sections               (reports black-screen regression)
PASS: zero page/console errors                        (incl. WS /api/ws/sites/.../live handshake)
ACCEPTANCE_OK
```

### 7. Docker production stack — built, started, acceptance-tested
```
$ docker compose build            # backend (python:3.12-slim + torch/ultralytics),
                                   # frontend (node build -> nginx), postgres pulled
$ docker compose up -d
Container buildsure-postgres   Healthy   (postgres:16-alpine, pg_isready)
Container buildsure-backend    Healthy   (gunicorn/uvicorn worker, alembic upgrade)  [200 /api/health db:ok]
Container buildsure-frontend   Healthy   (nginx, wget probe via proxy)               [200 /api/health]
Frontend published on http://localhost:8080
```
Browser E2E on the real stack (`http://localhost:8080`, same-origin `/api`):
```
PASS: login page renders brand
PASS: demo quick-access card visible
PASS: login + dashboard renders with real data
PASS: executive report renders sections
PASS: zero page/console errors          (incl. authenticated /api/ws/sites/../live handshake through nginx)
ACCEPTANCE_OK
```
API / pipeline acceptance through nginx (`http://localhost:8080/api`):
```
POST /auth/login                    -> token
POST /video/analyze (sample.mp4)    -> {"status":"queued", analysis_id}
GET  /video/analysis/{id}           -> queued -> completed   (sample lacks people; zero-detect evidence path)
POST /sites/{site}/reports/generate -> 200 EXECUTIVE RISK SUMMARY (after a completed analysis)
WS   /api/ws/sites/{site}/live      -> {"status":"STOPPED"} snapshots (no fabricated data)
```

### 8. Bugs found and fixed while exercising the container
- `ModuleNotFoundError: ai` — backend image was built from `./backend` but the app imports the top-level `ai`
  package. Backend build context moved to the repo root (`COPY backend/ .` + `COPY ai/ /app/ai`, `PYTHONPATH=/app`).
- `ImportError: libxcb.so.1` — `ultralytics` pulls the GUI `opencv-python`, colliding with `opencv-python-headless`.
  Added `libgl1 libglib2.0-0` and force the headless build (`pip uninstall opencv-python` + reinstall).
- Alembic `ValueError: invalid interpolation syntax` — encoded `%` in passwords blew up ConfigParser;
  `alembic/env.py` now escapes `%` as `%%` for `set_main_option`.
- `NameError: DEFAULT_VIDEO_SOURCE` — `live.py` referenced an unimported config constant on every WS connect;
  imported it from `app.config` (WS now handshakes and streams STOPPED snapshots).
- `'NoneType' object has no attribute 'get'` — `SafetyAgent` crashed when the report's `accident_zones` had
  `top_accident_zone: None` (empty-evidence video). Guarded with `or {}` in `safety_agent/agent.py`.
- `cannot access local variable 'logging'` — a nested `import logging` shadowed the outer logger; removed the
  redundant inner import and added a top-level `logging` + `logging.exception` on pipeline failures.
- `POSTGRES_PASSWORD` with special characters (`@`) would corrupt a literal DSN; compose now passes libpq-style
  env vars and `database.py` assembles the URL-encoded DSN (URL-safe passwords).

### 9. SQLite → PostgreSQL migration re-validated on a fresh DB then dropped
```
Total rows copied: 352, skipped 0
validate_migration.py: all FK pairs OK, seed anchors present, Status: OK
```

## Phases Addressed (26-phase spec)

| Phase | Item | Result |
|------|------|--------|
| 4    | JWT_SECRET_KEY required in production (fail-fast) | Done + verified |
| 5    | Single backend port 8000 everywhere (dev proxy, nginx, compose) | Done + repo-wide sweep clean |
| 9    | /api/health 503 degraded path wired into HEALTHCHECKs | Done + verified |
| 11   | Login rate limiting (sliding window, in-process) | Done + 429 verified |
| 13   | N+1 fixes: dashboard zone aggregates; reports selectinload(analysis) | Done |
| 14   | Production Docker topology (backend/frontend/nginx/compose) | Done + built + started + acceptance-tested |
| 15-17| Upload size cap + extension whitelist + 400/413 handling | Done + verified |
| 19-20| DATABASE_URL / libpq env injected from compose; CORS env | Done |
| 21-23| Background analysis, queued API, frontend wait-for-analysis + demo gating | Done + E2E verified |
| 26   | This report + committed changes | Completed |

## Deviations / Notes

- The container image does not bundle the demo construction video (`Contruction_vid.mp4`); operators provide it
  via the UI upload or `VIDEO_SOURCE`/volume mount. Uploads and zero-evidence analyses are fully covered by tests.
- Rate limiter resets on process restart (documented; in-process by design).
- Absolute `VITE_API_URL` must include the `/api` suffix (documented in `.env.example` / README).
- nginx `client_max_body_size 500m` must be raised if `MAX_UPLOAD_SIZE_MB` rises above 500.
- M1–M4 behavior preserved: no AI pipeline rewrite, no UI replacement, no data fabrication (missing evidence marked NOT_AVAILABLE).