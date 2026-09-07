# DevOps and deploy

## 1. Render (backend)

| Setting | Value |
|---|---|
| Type | Web Service, Docker |
| Root Directory | `backend/` |
| Region | Frankfurt |
| Plan | Free at start |
| Health Check | `/api/health` |
| Build Filter | `backend/**` (changes in frontend/docs don't trigger redeploy) |

`backend/Dockerfile` with `ca-certificates` (SSL to Supabase), `uvicorn` binding to `0.0.0.0:$PORT`.

**Decision: NO separate Render Background Worker.** Plan generation in the same web process (`BackgroundTasks`), the `plan_generation_jobs`/`plan_generation_job_personas` table gives visibility/retry/partial-success without needing a second service. Justification and migration threshold: [`../adr/decisions.md`](../adr/decisions.md#adr-1-generowanie-planu-bez-osobnego-workera).

**To be verified empirically after the first deploy:** whether an active `BackgroundTasks` (without an open HTTP request) counts as "traffic" protecting Render Free from autosleep after 15 min of inactivity. If not — a long job may be interrupted mid-way; the reaper on app startup marks it as `error` (user clicks "regenerate" manually in MVP, no automatic requeue).

## 2. SSE on Render Free

Real problem: the proxy drops idle SSE connections. Solution: heartbeat every 15s (`sse-starlette` has this built in via `ping=15`), `Cache-Control: no-cache`, `X-Accel-Buffering: no`. To be confirmed empirically with simulated 20–30 s silence before production.

## 3. Vercel (frontend)

| Setting | Value |
|---|---|
| Framework | Vite |
| Root Directory | `frontend/` |
| Build/Output | `npm run build` / `dist` |
| Env prefix | `VITE_` |
| Plan | **Hobby** (confirmed — 2–5 user scale, non-commercial use) |
| Ignored Build Step | skips build when changes are only in `backend/`/`docs/`/`supabase/` |

SPA (Vite), no Vercel Serverless Functions — API calls directly from the browser to Render.

**SPA fallback:** `frontend/vercel.json` with `rewrites` → `/index.html` (React Router `createBrowserRouter`). Without this, refreshing `/settings`, `/personas` etc. ends with `404: NOT_FOUND` on Vercel CDN.

## 4. Local run — REQUIRED (backend and frontend)

Full checklist in [`local-setup.md`](local-setup.md). Rule: the project must run locally without Docker and without deploy — production is not the only way to work.

## 5. Secrets and environment variables

| Variable | Where it lives | Notes |
|---|---|---|
| `DATABASE_URL` | local `.env` (localhost:5432 or Supabase dev) / Render | Render: through Supavisor pooler, not directly `db.<ref>.supabase.co` (IPv6-only) |
| `SUPABASE_URL` | local / Render | |
| `SUPABASE_JWKS_URL` | local / Render | `PyJWKClient(cache_keys=True, lifespan=300)` — cache, no fetch per request |
| `SUPABASE_SERVICE_ROLE_KEY` | **only** Render (secret) | Backend-only, Admin API. Never in repo/frontend |
| `OPENROUTER_API_KEY` | Render (secret) | |
| `OPENROUTER_CHAT_MODEL` / `OPENROUTER_PLANNER_MODEL` | Render + `.env.example` | env-driven, not hardcoded |
| `CHAT_HARD_TIMEOUT_S` / `CHAT_ROUND_TIMEOUT_S` | Render + `.env.example` | SSE whole-turn (default 210) / per LLM round (default 90) |
| `CORS_ORIGINS` | Render | `https://goat.fmazurkiewicz.dev` (+ `http://localhost:3000` when testing API locally) + regex `*.vercel.app` for preview |
| `ADMIN_EMAILS` | local / Render | Comma-separated extras auto-approved on `profiles` INSERT only (ADR-22). Sole admin `fmazurkiewicz@gmail.com` is always included. |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL` | Vercel + `frontend/.env.local` | Public, safe in bundle (protected by RLS) |
| `APP_VERSION` | optionally Render/Vercel build | Overrides `backend/VERSION` (semver); default file in repo |

Rules: `SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`, `DATABASE_URL`, `SUPABASE_ACCESS_TOKEN` (CLI) — never in repo/frontend. `.gitignore` covers `.env`, `.env.*` except `!.env.example`, `frontend/.env.local`, and **`/graft/`** (local Graft cache — ADR-20; not CI, not deploy).

### Semver versioning (Admin panel)

| Artifact | Role |
|---|---|
| `backend/VERSION` | **Single source of truth** — e.g. `0.2.0` (MAJOR.MINOR.PATCH) |
| `backend/pyproject.toml` + `frontend/package.json` | Keep aligned with `VERSION` (informational) |
| Admin → App version | Displays **v{semver}**; GitHub commit as diagnostic metadata |

On release: bump `backend/VERSION`, synchronize `pyproject.toml` / `package.json`, commit, deploy FE + BE. Format: `X.Y.Z` or pre-release `X.Y.Z-beta.1`.

## 6. Supabase migrations

Supabase project: **`goat`** (one cloud at start; separate `goat-dev` only when you consciously split environments). `supabase/migrations/*.sql` as the single source of truth (**not** Alembic).

1. Cloud (current setup): migrations via SQL Editor or `supabase link` + `supabase db push` — see [`cloud-setup.md`](cloud-setup.md).
2. CI (`migrations-check` on every PR): Postgres in a CI container, applying all migrations from scratch.
3. Subsequent migrations to prod: **manual, conscious step**, not auto-applied on push to main.

## 7. Authentication — Google OAuth (no magic link)

**Decision:** Google OAuth only via Supabase Auth. Redirects: `https://goat.fmazurkiewicz.dev/**` (prod); add `http://localhost:3000/**` when you go back to local. Details: [`cloud-setup.md`](cloud-setup.md).

## 8. CI/CD — `.github/workflows/ci.yml`

Jobs (path-filtered except secret-scan):
- `backend-lint-test` — `ruff check`, `ruff format --check`, `mypy` (min. `domain/`, `llm/`), `pytest`.
- `frontend-lint-build` — `eslint`, `npm test` (Vitest), `vite build`.
- `migrations-check` — Postgres in a CI container, applying all migrations from scratch.
- `secret-scan` — TruffleHog `--only-verified` on the git history.

Dependabot (weekly): npm `/frontend`, pip `/backend`, Docker `/backend`, GitHub Actions `/`.

Deploy to prod automatically via native Render/Vercel integrations after merge; prod migrations remain a manual step (section 6).

## 9. Monitoring

Render logs (built-in), Sentry free tier (backend Python SDK + frontend React SDK), health check monitored natively by Render, spending limit set in OpenRouter panel (soft limit + email alert) — without building your own alerting infrastructure.

**Cold start (ADR-19):** SPA shows the lamp when, in the wake-up window, `GET /api/health`
doesn't return for ≥ 2 s. After 200 (or ~90 s / background tab) **zero** further pings — Render
Free should sleep after 15 min. This is UX, not keep-alive. Spec:
[`../superpowers/specs/2026-08-16-api-status-lamp-design.md`](../superpowers/specs/2026-08-16-api-status-lamp-design.md).

## 10. Cloudflare DNS

| Type | Name | Value | Proxy |
|---|---|---|---|
| CNAME | `goat` | `cname.vercel-dns.com` | DNS only |
| CNAME | `api-goat` | `<service>.onrender.com` | DNS only (double proxy conflicts with SSE) |

## 11. Cost

~$0–10/month at the dev/test stage (OpenRouter only). First paid threshold: **Supabase Pro $25/month** when leaving pure testing (Free pauses the project after 7 days of inactivity). Render Starter $7/month only when cold start really bothers. Without Render Worker (decision) — that cost doesn't exist at all.

## 12. Out of MVP scope

Garmin/Strava/Apple Health import/sync — "maybe someday", no impact on architecture now (the generic `results` model will carry it).
