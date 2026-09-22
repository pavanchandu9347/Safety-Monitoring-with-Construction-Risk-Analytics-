# Phase 26 — Production-Hardening Verification Report

Status: **COMPLETE** (with one environment constraint noted below)
Date: 2026-09-22

## Scope

Production hardening of BuildSure (M1–M4) across phases: single backend port, health/degradation, secret
handling, login rate limiting, N+1 query elimination, production Docker topology (Nginx + Gunicorn/Uvicorn +
PostgreSQL), upload limits/whitelist, background video analysis with a queued API contract, demo gating,
frontend/backend automated tests, documentation, and a production-like end-to-end acceptance run.

Constraint (unchanged from previous sessions): **no `docker` binary exists on this machine**, so the Docker
artifacts are written and diff-reviewed but could not be built/started here (`docker compose up --build` must be
run by the team on a Docker host). Everything that can be verified without Docker was executed and is evidenced
below.

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

### 6. SQLite → PostgreSQL migration re-validated on a fresh DB then dropped
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
| 14   | Production Docker topology (backend/frontend/nginx/compose) | Written (not executed — no docker) |
| 15-17| Upload size cap + extension whitelist + 400/413 handling | Done + verified |
| 19-20| DATABASE_URL re-injected from env; CORS env for compose | Done |
| 21-23| Background analysis, queued API, frontend wait-for-analysis + demo gating | Done + E2E verified |
| 26   | This report + committed changes | In progress → completed |

## Deviations / Notes

- Docker artifacts unexecuted (constraint above); `frontend/Dockerfile` requires `npm ci` — lockfile updated.
- Rate limiter resets on process restart (documented; in-process by design).
- Absolute `VITE_API_URL` must include the `/api` suffix (documented in `.env.example` / README).
- nginx `client_max_body_size 500m` must be raised if `MAX_UPLOAD_SIZE_MB` rises above 500.
- M1–M4 behavior preserved: no AI pipeline rewrite, no UI replacement, no data fabrication (missing evidence marked NOT_AVAILABLE).