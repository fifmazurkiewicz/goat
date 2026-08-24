# Local setup

**Currently we set up the cloud** — full path: [`cloud-setup.md`](cloud-setup.md) (Supabase project **`goat`**).

This document: local loop (backend/frontend on the machine + the same Supabase `goat` project, or in the future a local Postgres). No Docker.

---

## A. Supabase — the same `goat` project (already from cloud-setup)

If the `goat` project and migrations are already in the cloud, **don't create a second project**. Use the same keys / pooler from [`cloud-setup.md`](cloud-setup.md) §1.4.

If you're starting from scratch locally only (no deploy):

### A1. Project

1. [supabase.com](https://supabase.com) → **New project**.
2. Name: **`goat`** (not `coach-dev`).
3. Database password: **generate and save it**.
4. Region: e.g. **Frankfurt**.
5. Active → save the **Reference ID** (`<ref>`).

### A2. Google OAuth (Google Cloud + Supabase)

**Google Cloud Console** ([console.cloud.google.com](https://console.cloud.google.com)):

1. Create / select a GCP project.
2. APIs & Services → **OAuth consent screen** → External → fill in the app name, your email → Save.
3. APIs & Services → **Credentials** → Create credentials → **OAuth client ID** → Application type: **Web application**.
4. Authorized JavaScript origins: `http://localhost:3000`
5. Authorized redirect URIs:  
   `https://<ref>.supabase.co/auth/v1/callback`
6. Create → copy the **Client ID** and **Client Secret**.

**Supabase Dashboard:**

1. Authentication → **Providers** → **Google** → Enable.
2. Paste the Client ID and Client Secret → Save.
3. Authentication → **URL Configuration** — for local, add alongside prod:
   - Redirect URLs: `http://localhost:3000/**` (Site URL can stay `https://goat.fmazurkiewicz.dev`).

### A3. Migrations (SQL Editor — no CLI)

1. In the repo open these files:
   - `supabase/migrations/0001_init.sql`
   - `supabase/migrations/0002_exercise_catalog.sql`
2. Supabase → **SQL** → **New query**.
3. Paste the **entire** content of `0001_init.sql` → **Run** (must succeed without errors).
4. New query → paste the **entire** content of `0002_exercise_catalog.sql` → **Run**.
5. Next migrations (if not already on the project): `0007_running_metrics_strength.sql`, `0008_background_jobs.sql`, `0009_persona_role_boundaries.sql`, `0010_drop_personas_chat_model.sql`, `0011_invoked_via_multi_slash.sql`, `0012_exercise_catalog_source_nullable.sql`, `0013_exercise_catalog_seed_free_exercise_db.sql` — each in a separate query, **Run**. `0013` is large (~0.9 MB) and generated (`photo_path` = path in the bucket) — see "Exercise catalog import" below.
6. **Table Editor** — should include:
   - `profiles`, `personas`, `persona_templates`, `plan_templates`, `allowed_metrics`
   - `chat_sessions`, `chat_messages`, `results`, `plans`, `plan_items`
   - `usage_limits`, `exercises`, `background_jobs`
7. Check seed: `persona_templates` and `exercises` have rows.

### A4. Copy the connection string and keys

**Database** (Project Settings → Database):

1. Connection string → **URI**.
2. Choose **Connection pooling** (Supavisor), mode **Transaction**, port **6543**.
3. Copy the URI and replace `[YOUR-PASSWORD]` with the password from A1.  
   Example shape (host/region may differ — take from UI):

```text
postgresql://postgres.<ref>:<PASSWORD>@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

For the backend add the dialect: `postgresql+asyncpg://...` (replace the `postgresql://` prefix with `postgresql+asyncpg://`).

**API** (Project Settings → API):

| Panel field | Where you paste |
|---|---|
| Project URL | `SUPABASE_URL`, `VITE_SUPABASE_URL` |
| `anon` `public` | `VITE_SUPABASE_ANON_KEY` |
| `service_role` `secret` | `SUPABASE_SERVICE_ROLE_KEY` (backend only!) |

JWKS (fixed pattern):

```text
https://<ref>.supabase.co/auth/v1/.well-known/jwks.json
```

---

## B. OpenRouter (LLM)

1. [openrouter.ai](https://openrouter.ai) → account → API Keys → Create key.
2. Save the key (will go into `OPENROUTER_API_KEY` in the backend).
3. Optionally: set a soft spending limit + email alert.

---

## C. Env files (local, do not commit)

Locally: **Postgres on localhost** + **email/password login** (without Supabase OAuth).  
Render/Vercel: **Google OAuth** + Supabase JWKS (without dev login).

### C1. Backend

```powershell
cd C:\Users\MSI\PycharmProjects\goat\backend
copy .env.example .env
```

Edit `backend/.env`:

```env
ENVIRONMENT=local

DATABASE_URL=postgresql+asyncpg://postgres:<PASSWORD>@localhost:5432/goat

DEV_AUTH_EMAIL=<your-email>
DEV_AUTH_PASSWORD=<your-password>
DEV_AUTH_USER_ID=00000000-0000-4000-8000-000000000001
LOCAL_JWT_SECRET=<random-string>

OPENROUTER_API_KEY=<key from OpenRouter>
OPENROUTER_CHAT_MODEL=anthropic/claude-haiku-4.5
OPENROUTER_PLANNER_MODEL=anthropic/claude-sonnet-4.6

CORS_ORIGINS=http://localhost:3000
```

`SUPABASE_*` **are not required locally** — leave them commented / empty.

### C2. Frontend

```powershell
cd C:\Users\MSI\PycharmProjects\goat\frontend
copy .env.example .env.local
```

Edit `frontend/.env.local`:

```env
VITE_ENABLE_DEV_LOGIN=true
VITE_API_BASE_URL=http://localhost:8000
```

`VITE_SUPABASE_*` **are not required locally** with `VITE_ENABLE_DEV_LOGIN=true`.

Never commit `.env` / `.env.local` and don't paste secrets into chat.

---

## D. Running the processes

### D1. Backend (terminal 1)

```powershell
cd C:\Users\MSI\PycharmProjects\goat\backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### D2. Frontend (terminal 2)

```powershell
cd C:\Users\MSI\PycharmProjects\goat\frontend
npm install
npm run dev
```

Frontend: `http://localhost:3000`  
API: `http://localhost:8000`

---

## E. Smoke test

1. `curl http://localhost:8000/api/health` → `200` / `{"status":"ok"}` (or equivalent).
2. Browser → `http://localhost:3000` → **Sign in** (email/password from `DEV_AUTH_*`).
3. Create a persona from a template.
4. **General conversation** → "Generate a harmonized plan for August" → **Goat · Team Lead** (not the dietitian); result in the Plans tab.
5. (Optionally) generate a weekly plan → job status `success` / `partial_success`.
6. Check `/results` and `/settings`.

---

## E2. Exercise catalog import (free-exercise-db)

The catalog is seeded by migration **`0013`** (a generated file in the repo — don't run the import to get data). You only re-run the script when updating the dataset:

```powershell
# 1. Download the dataset + generate 0013 (no secrets, no DB)
cd backend; uv run python ../scripts/import_free_exercise_db.py

# 2. (optional) PL translations via LLM — requires a real OPENROUTER_API_KEY
uv run python ../scripts/translate_exercises.py        # cache: .tmp/free-exercise-db-translations.json
uv run python ../scripts/import_free_exercise_db.py    # regenerate 0013 with PL

# 3. (optional) Photos to Supabase Storage — requires SUPABASE_URL + SERVICE_ROLE_KEY
uv run python ../scripts/import_free_exercise_db.py --upload-photos
```

After regeneration: commit `0013_*.sql`, then Run in SQL Editor (local and cloud).
Re-import existing data: `DELETE FROM exercises WHERE source='free_exercise_db';` → rerun `0013`.

---

## F. For later — local Postgres instead of Supabase DB

When you want `DATABASE_URL` on `localhost` (Auth can stay on Supabase Cloud):

1. Postgres 16 locally → `CREATE DATABASE goat;`
2. Stub `auth` (as in CI `.github/workflows/ci.yml`) — `pgcrypto` + `auth.users` + `auth.uid()`.
3. **Role `service_role` (NOLOGIN)** — it exists in Supabase right away, in a clean Postgres it doesn't; without it `app/main.py:lifespan` dies on `SET LOCAL ROLE service_role` (`role "service_role" does not exist`). Migration `0001` does **not** create it (it only uses it in `GRANT`s).
4. `psql -f supabase/migrations/0001_init.sql` then `0002_exercise_catalog.sql` and the rest (`0007`–`0011`).
5. `DATABASE_URL=postgresql+asyncpg://postgres:...@localhost:5432/goat`
6. After the first Google login, insert the UUID from the JWT (`sub`) into the local `auth.users` (FK).

Steps 2–3 (bootstrap before migrations, `psql`):

```sql
create extension if not exists pgcrypto;
create schema if not exists auth;
create table if not exists auth.users (
  id uuid primary key default gen_random_uuid(),
  email text
);
-- Mirror auth.uid() from Supabase so RLS policies can be created locally.
create or replace function auth.uid() returns uuid as $$
  select nullif(current_setting('request.jwt.claims', true)::json->>'sub', '')::uuid
$$ language sql stable;
-- Required by the backend (SET LOCAL ROLE) and the GRANTs in migrations.
create role service_role nologin;
```

These details aren't needed for the first setup — come back here only when you intentionally switch DB.

---

## G. Graft — code map for the agent (ADR-20)

Local context graph ([NanoNets/Graft](https://github.com/nanonets/graft)). **Not part of runtime** — not needed for `uvicorn` / `npm run dev` / deploy. The agent uses it instead of blind grep.

### G1. First time (this machine / this repo)

```powershell
npx @nanonets/graft init --agents cursor --dry-run
npx @nanonets/graft init --agents cursor
npx @nanonets/graft telemetry disable
npx @nanonets/graft build
```

`init --agents cursor` writes only:

| File | Commit? |
|---|---|
| `.cursor/rules/graft.mdc` | yes (wiring) |
| `.cursor/mcp.json` | yes (MCP, no secrets) |
| `graft/` | **no** — cache; `graft build` adds `/graft/` to `.gitignore` |

Restart Cursor so MCP loads.

### G2. When to run `graft build`

| When | Command |
|---|---|
| Session start when the graph is out of sync | `npx @nanonets/graft check` → on exit 1: `npx @nanonets/graft build` |
| After merge / large refactor / many files | `npx @nanonets/graft build` |
| `ask` / `callers` look stale | `npx @nanonets/graft build` |

Not after every line — regular queries refresh structure on their own (~3 ms, $0).

### G3. Optionally `--deep` (LLM)

Only consciously. The key **locally** (not in chat, not in commit). Placeholders:

| Variable | Example |
|---|---|
| `GRAFT_PROVIDER` | `openai` (OpenAI-compatible wire format) |
| `GRAFT_BASE_URL` | `https://openrouter.ai/api/v1` |
| `GRAFT_API_KEY` | set locally |
| `GRAFT_MODEL` | a model from OpenRouter |

Then: `npx @nanonets/graft build --deep`.

---

## Checklist (first time)

| # | Step | OK? |
|---|---|---|
| 1 | Supabase **`goat`** project Active (usually already from cloud-setup) | |
| 2 | Google OAuth in GCP + Supabase Providers | |
| 3 | Site URL / Redirect `localhost:3000` | |
| 4 | SQL: `0001_init` + `0002` + `0007`–`0011` if missing | |
| 5 | Table Editor: tables + seed | |
| 6 | OpenRouter API key | |
| 7 | `backend/.env`: localhost + `DEV_AUTH_*` (without Supabase) | |
| 8 | `frontend/.env.local`: `VITE_ENABLE_DEV_LOGIN=true` | |
| 9 | `uv run uvicorn` on :8000 | |
| 10 | `npm run dev` on :3000 | |
| 11 | Health + email/password login + persona + chat | |
| 12 | (optional, tooling) Graft: `init --agents cursor` + `telemetry disable` + `build` — §G | |
