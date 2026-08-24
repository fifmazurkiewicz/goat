# Cloud setup — project `goat` (detailed)

Order matters: **Supabase → OpenRouter → Render → Vercel → Cloudflare → wrap-up**.

| Layer | Host |
|---|---|
| Frontend | `goat.fmazurkiewicz.dev` |
| API | `api-goat.fmazurkiewicz.dev` |

Project name: **`goat`**. Local loop: [`local-setup.md`](local-setup.md) — later.

Keep in a notebook (not in repo / not in chat with secrets):

- Supabase database password
- Reference ID (`<ref>`)
- Project URL, `anon` key, `service_role` key
- pooler connection string
- OpenRouter API key
- Render service URL (`*.onrender.com`)

---

## Step 1 — Supabase: create the project

1. Go to [https://supabase.com](https://supabase.com) and log in.
2. Click **New project** (or **Start a new project**).
3. Choose an organization (or create a new one).
4. In the form:
   - **Name:** `goat` (exactly this — not `coach`, not `coach-dev`).
   - **Database Password:** click Generate password or enter your own. **Copy and save it right away** — you won't see it in clear text later.
   - **Region:** choose the closest, prefer **Frankfurt (eu-central-1)** or West EU.
   - Pricing: Free (enough to start).
5. Click **Create new project**.
6. Wait 1–2 minutes until the project status is green / **Active** (not Provisional / Setting up).
7. In the left menu at the bottom (gear icon) → **Project Settings** → **General** tab.
8. Copy **Reference ID** — a short string like `abcdefghijklmnopqrst`. This is your `<ref>`.
9. Also save the **Project URL** from this page / API — usually `https://<ref>.supabase.co`.

---

## Step 2 — Google Cloud: OAuth client

Without this, the "Sign in with Google" button in the app won't work.

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com).
2. At the top choose an existing GCP project or **New Project**:
   - GCP project name can be `goat` (this is a separate name from Supabase — can be the same).
   - Create → wait → select this project in the selector.
3. In the menu (☰) → **APIs & Services** → **OAuth consent screen**.
   - If Google shows a new flow "Google Auth Platform" / Branding — enter the consent screen configuration.
4. User type: **External** → Create.
5. Fill in the minimum:
   - App name: `goat`
   - User support email: your email
   - Developer contact: your email
   - Save and Continue through Scopes (you can add nothing for MVP) → Test users (optionally add yourself, if the app is in Testing) → Back to Dashboard.
6. **APIs & Services** → **Credentials** → **+ Create credentials** → **OAuth client ID**.
7. Application type: **Web application**.
8. Name: e.g. `goat-web`.
9. **Authorized JavaScript origins** → Add URI:
   - `https://goat.fmazurkiewicz.dev`
   - (later local) `http://localhost:3000`
10. **Authorized redirect URIs** → Add URI:
    - `https://<ref>.supabase.co/auth/v1/callback`  
      (enter your `<ref>` from Step 1 — no spaces, with `https://`)
11. Click **Create**.
12. The window will show **Client ID** and **Client Secret** — copy both and save.  
    (Secret later: Credentials → click the client → Client secrets.)

---

## Step 3 — Supabase: enable Google + URLs

1. Go back to the Dashboard of the **goat** project on Supabase.
2. Left menu → **Authentication** → **Providers**.
3. Find **Google** → click the row / Edit.
4. Toggle **Enable Sign in with Google** to enabled.
5. Paste:
   - **Client ID** from Google Cloud
   - **Client Secret (for OAuth)** from Google Cloud
6. **Save**.
7. Still in Authentication → **URL Configuration** (sometimes under **Authentication → Settings**).
8. Set:
   - **Site URL:** `https://goat.fmazurkiewicz.dev`
   - **Redirect URLs:** click Add / add exactly to the field:
     - `https://goat.fmazurkiewicz.dev/**`
9. **Save**.  
   (When the domain doesn't work yet, you can temporarily set Site URL to the Vercel URL `https://….vercel.app` and also add it to Redirect URLs — then return to `goat.fmazurkiewicz.dev` later.)

---

## Step 4 — Supabase: reset (optional) + migrations in SQL Editor

If the database has old tables / partial seed — **first wipe**, then fresh init.

### 4a. Wipe (when resetting the environment)

1. Open `supabase/reset_public.sql`.
2. Supabase → **SQL** → **SQL Editor** → New query → paste the whole thing → **Run**.
3. Confirm success. Deletes tables in `public` + `app_private` schema (application data). `auth.users` accounts remain.
4. If you use the CLI `supabase db push`: also clean `supabase_migrations.schema_migrations` (comment in the wipe file).

### 4b. Init

1. On disk:
   - `supabase/migrations/0001_init.sql` (schema + behavior seed + `app_private` safety)
   - `supabase/migrations/0002_exercise_catalog.sql`
2. SQL Editor → New query → paste the **entire** content of `0001_init.sql` → **Run**.
3. New query → paste the **entire** content of `0002_exercise_catalog.sql` → **Run**.
4. (Existing DB without wipe) New query → `0007_running_metrics_strength.sql` → **Run**
   (running metrics under `strength` / Training tab; fresh `0001_init` already has it in seed).
5. **Mandatory before deploying backend from `main` (2026-08-04+):** New query →
   `0008_background_jobs.sql` → **Run** — without this the API starts, but background jobs (LLM titles,
   harmonization after upsert) don't work; after the startup fix missing migrations don't block health.
6. Subsequent migrations (each in a separate query, **Run**): `0009_persona_role_boundaries.sql`,
   `0010_drop_personas_chat_model.sql`, `0011_invoked_via_multi_slash.sql`,
   `0012_exercise_catalog_source_nullable.sql`,
   **`0013_exercise_catalog_seed_free_exercise_db.sql`** (large ~0.9 MB, generated — import
   of 868 PL exercises; `photo_path` = path in bucket, not full URL).
7. Table Editor — should include:
   - `profiles`, `personas`, `persona_templates`, `plan_templates`, `allowed_metrics`
   - `user_profile`, `chat_sessions`, `chat_messages`, `results`
   - `plans`, `plan_items`, `plan_generation_jobs`, `plan_generation_job_personas`
   - `usage_limits`, `moderation_events`, `admin_audit_log`, `exercises`
5. `persona_templates` — rows with professional `default_prompt` (without "What you do NOT do" block).
6. Schema `app_private` / table `persona_template_safety` — visible for the service role; **not** via regular Table Editor as `authenticated` (intentional).

There is no longer a `0003_professional_templates.sql` file — contents are in `0001`.

---

## Step 5 — Supabase: connection string and API keys

### 5a. Connection string (for Render / `DATABASE_URL`)

1. Project Settings (gear) → **Database**.
2. **Connection string** section (or Connect → ORMs / Connection pooling — UI changes).
3. Choose:
   - type: **URI**
   - method: **Connection pooling** / **Pooler**
   - mode: **Transaction**
   - port: **6543** (not 5432)
4. Copy the string. It looks something like:

```text
postgresql://postgres.<ref>:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

Take the host (`aws-0-….pooler.supabase.com`) **exactly from the panel** — don't guess the region.
5. Replace `[YOUR-PASSWORD]` with the password from Step 1. If the password has special characters (`@`, `#`, `%`…), they must be **URL-encoded** (e.g. `@` → `%40`).
6. For the backend, change the prefix:
   - from: `postgresql://`
   - to: `postgresql+asyncpg://`  
   This will be the value of `DATABASE_URL`.

### 5b. API keys

1. Project Settings → **API**.
2. Copy and save:
   - **Project URL** → `https://<ref>.supabase.co` = `SUPABASE_URL` / `VITE_SUPABASE_URL`
   - **anon** `public` key (long JWT) → `VITE_SUPABASE_ANON_KEY` (frontend / Vercel only)
   - **service_role** `secret` key → `SUPABASE_SERVICE_ROLE_KEY` (**only** Render; never to Vercel / frontend / repo)
3. JWKS (fixed pattern — you don't copy from the panel, you build from `<ref>`):

```text
https://<ref>.supabase.co/auth/v1/.well-known/jwks.json
```

This is `SUPABASE_JWKS_URL`.

---

## Step 5b — Supabase Storage: bucket `exercise-photos`

Photos of the exercise catalog (free-exercise-db import) live in Storage — re-init of the database **does not** clean Storage:

1. Supabase → **Storage** → **New bucket**.
2. Name: `exercise-photos` | Public bucket: **YES** (`<img src>` doesn't send JWT — without public access photos won't render).
3. Policies: **NO** INSERT/UPDATE/DELETE for `authenticated`/`anon` (default deny) — upload only via service role key, locally from the script.
4. Upload: `cd backend; uv run python ../scripts/import_free_exercise_db.py --upload-photos`
   (requires `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` in env; ~868 JPG files, ~50–100 MB).
   Re-upload under the same paths is safe (overwrite of the same content).

---

## Step 6 — OpenRouter

1. Go to [https://openrouter.ai](https://openrouter.ai) → log in / sign up.
2. Menu → **Keys** (or Settings → Keys).
3. **Create Key** → name e.g. `goat-prod` → Create.
4. Copy the key immediately (`sk-or-…`) → this is `OPENROUTER_API_KEY`.
5. Recommended: Settings / Credits → set **soft limit** monthly + email alert, so you don't blow the budget.

---

## Step 7 — Render: Web Service (backend)

### 7a. Create the service

1. Go to [https://dashboard.render.com](https://dashboard.render.com) → log in (preferably with the same GitHub as the repo).
2. **New +** → **Web Service**.
3. Connect the **`fifmazurkiewicz/goat`** repository (Authorize GitHub if needed) → Connect.
4. Fill the form:

| Field | Value |
|---|---|
| Name | `goat-api` |
| Language / Runtime | **Docker** |
| Branch | `main` |
| Region | **Frankfurt** (if available; otherwise closest EU) |
| Root Directory | `backend` |
| Dockerfile Path | `./Dockerfile` (relative to Root Directory — i.e. `backend/Dockerfile`) |
| Instance type | **Free** |

5. **Health Check Path:** `/api/health` (Advanced / Health — depending on UI).
6. **Auto-Deploy:** Yes (deploy on push to `main`).

### 7b. Environment variables (before first Deploy)

In the **Environment** section add one by one (key = value), **without** quotes:

| Key | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | string from Step 5a (`postgresql+asyncpg://…`) |
| `SUPABASE_URL` | `https://<ref>.supabase.co` |
| `SUPABASE_JWKS_URL` | `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json` |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role from Step 5b |
| `OPENROUTER_API_KEY` | key from Step 6 |
| `OPENROUTER_CHAT_MODEL` | `anthropic/claude-haiku-4.5` |
| `OPENROUTER_PLANNER_MODEL` | `anthropic/claude-sonnet-4.6` |
| `CORS_ORIGINS` | `https://goat.fmazurkiewicz.dev` |

At start, before DNS works, you can temporarily set:

```text
CORS_ORIGINS=https://goat.fmazurkiewicz.dev,https://YOUR-PROJECT.vercel.app
```

(The regex `*.vercel.app` is in the backend code anyway — but an explicit domain in `CORS_ORIGINS` doesn't hurt.)

### 7c. Deploy and verify

1. Click **Create Web Service** / **Deploy**.
2. Open the **Logs** tab — wait for the Docker build to complete and the uvicorn start to appear.
3. Copy the public URL of the service, e.g. `https://goat-api.onrender.com` (exact name from the panel).
4. In browser or PowerShell:

```powershell
curl https://goat-api.onrender.com/api/health
```

Expected: HTTP 200 and JSON with OK status (Free tier: first launch may take 30–60 s — cold start).
5. **Custom Domain** in Render, leave for Step 10 (after Cloudflare).

---

## Step 8 — Vercel: frontend

### 8a. Import project

1. Go to [https://vercel.com](https://vercel.com) → log in (GitHub).
2. **Add New…** → **Project** → select the **`goat`** repo.
3. Configure:
   - **Framework Preset:** Vite
   - **Root Directory:** click Edit → select the **`frontend`** folder → Continue
   - Build Command: `npm run build` (Vite default)
   - Output Directory: `dist`
   - Install Command: `npm install`
4. **Environment Variables** — add for Environment: **Production** (and Preview if you want):

| Name | Value |
|---|---|
| `VITE_SUPABASE_URL` | `https://<ref>.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | anon key from Step 5b |
| `VITE_API_BASE_URL` | for now `https://goat-api.onrender.com` (URL from Step 7c) — after DNS change to `https://api-goat.fmazurkiewicz.dev` |

5. **Deploy**.
6. After success open `https://<name>.vercel.app` — the page should load (login may not yet return on the correct redirect, until you add this URL to Supabase Redirect URLs and Google origins).

The repo has `frontend/vercel.json` (`rewrites` → `/index.html`) — needed for React Router, so that **refreshing** a subroute (`/settings`, `/chat`, …) doesn't give Vercel 404.

### 8b. Temporary redirect under Vercel preview (optional)

If you test before `goat.fmazurkiewicz.dev` exists:

1. Supabase → Authentication → URL Configuration → add Redirect: `https://<name>.vercel.app/**`
2. Google Cloud → OAuth client → add JavaScript origin: `https://<name>.vercel.app`
3. Site URL you can set for a moment to the Vercel URL.

---

## Step 9 — Cloudflare DNS

The domain `fmazurkiewicz.dev` is already in Cloudflare (per the portfolio standard).

1. Go to [https://dash.cloudflare.com](https://dash.cloudflare.com) → zone **`fmazurkiewicz.dev`**.
2. **DNS** → **Records** → **Add record**.

**Frontend record:**

| Field | Value |
|---|---|
| Type | `CNAME` |
| Name | `goat` |
| Target | value from Vercel → Project → Settings → Domains (often `cname.vercel-dns.com`) |
| Proxy status | **DNS only** (grey cloud, not orange) |

3. **Add record** again — **API:**

| Field | Value |
|---|---|
| Type | `CNAME` |
| Name | `api-goat` |
| Target | Render hostname **without** `https://`, e.g. `goat-api.onrender.com` |
| Proxy status | **DNS only** (mandatory — orange proxy breaks SSE) |

4. Save. Propagation: usually a few minutes.

---

## Step 10 — Custom domains in Vercel and Render

### 10a. Vercel

1. Project `goat` → **Settings** → **Domains**.
2. Add: `goat.fmazurkiewicz.dev` → Add.
3. Vercel will show status — when DNS matches, **Valid** / SSL Active appears.
4. (Optionally) set this domain as Production.

### 10b. Render

1. Service `goat-api` → **Settings** → **Custom Domains**.
2. Add: `api-goat.fmazurkiewicz.dev`.
3. Wait for DNS verification + certificate.

### 10c. Env after DNS

1. **Vercel** → Environment Variables → edit:

```text
VITE_API_BASE_URL=https://api-goat.fmazurkiewicz.dev
```

2. Redeploy frontend (Deployments → … → Redeploy), because `VITE_*` are baked into the build.
3. **Render** → Environment → make sure:

```text
CORS_ORIGINS=https://goat.fmazurkiewicz.dev
```

4. **Supabase** → URL Configuration:
   - Site URL: `https://goat.fmazurkiewicz.dev`
   - Redirect: `https://goat.fmazurkiewicz.dev/**`
5. **Google Cloud** → OAuth client → JavaScript origin: `https://goat.fmazurkiewicz.dev` (kept).

---

## Step 11 — Production smoke test

Do in order:

1. **Health API**

```powershell
curl https://api-goat.fmazurkiewicz.dev/api/health
```

→ 200. If timeout on Free Render: wait ~1 min (cold start) and retry.

2. **Frontend** — open `https://goat.fmazurkiewicz.dev`.
3. **Google login** — passes consent → returns to the `goat` domain (not `redirect_uri_mismatch` error).
4. In Supabase → **Authentication → Users** — your account is visible.
5. Table Editor → **profiles** — row with `id` = user UUID (trigger from migration).
6. In the app: create a persona from a template.
7. Chat: send a message → tokens appear (SSE).
8. (Optionally) plan generation → job status ends in success / partial.

---

## Checklist

| # | What | OK? |
|---|---|---|
| 1 | Supabase project **`goat`** Active, `<ref>` and DB password saved | |
| 2 | Google OAuth client + redirect on `https://<ref>.supabase.co/auth/v1/callback` | |
| 3 | Supabase Provider Google ON + Site/Redirect under `goat.fmazurkiewicz.dev` | |
| 4 | SQL: `0001_init` + `0002_exercise_catalog` without errors, seed OK | |
| 5 | Pooler URI (`+asyncpg`) + anon + service_role + JWKS | |
| 6 | OpenRouter key (+ soft limit) | |
| 7 | Render Docker `backend/`, env, `/api/health` = 200 | |
| 8 | Vercel `frontend/`, three `VITE_*`, deploy OK | |
| 9 | Cloudflare CNAME `goat` + `api-goat`, **DNS only** | |
| 10 | Custom domains TLS + `VITE_API_BASE_URL` + `CORS_ORIGINS` | |
| 11 | Smoke: login + persona + chat | |

---

## Common problems

| Symptom | What to check |
|---|---|
| `redirect_uri_mismatch` | Google redirect URI = exactly `https://<ref>.supabase.co/auth/v1/callback`; Site/Redirect in Supabase = frontend domain |
| CORS error in browser | `CORS_ORIGINS` on Render contains the exact frontend origin (`https://goat.fmazurkiewicz.dev`) |
| API 502 / timeout first time | Render Free cold start — wait and refresh |
| DB / SSL error on Render | `DATABASE_URL` through **pooler :6543**, not direct host `db.<ref>.supabase.co`; prefix `postgresql+asyncpg://` |
| Chat "hangs", SSE dies | Cloudflare Proxy on `api-goat` must be **DNS only** |
| Login OK, but missing profile / FK | Migration 0001 didn't run or trigger on `auth.users` — check Table Editor |
| Frontend calls wrong API | After changing `VITE_*` you must **Redeploy** on Vercel |
| Refreshing `/settings` (etc.) → `404: NOT_FOUND` | Missing `frontend/vercel.json` SPA rewrite → `/index.html`; after adding Redeploy |
