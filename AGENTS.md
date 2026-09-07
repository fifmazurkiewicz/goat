## Commands

Root is a monorepo (`backend/`, `frontend/`, `supabase/migrations/`). Nested command lists: `backend/AGENTS.md`, `frontend/AGENTS.md`.

**Backend** (`cd backend`):

- Dev server: `uv run uvicorn app.main:app --reload --port 8000`
- Tests: `uv run pytest`
- Lint: `uv run ruff check .` and `uv run ruff format --check .`
- Types: `uv run mypy app/domain app/llm`

**Frontend** (`cd frontend`):

- Dev server: `npm run dev` (Vite, port 3000)
- Tests: `npm test` (Vitest)
- Lint: `npm run lint`
- Build: `npm run build`

**Graft** (agent code map, not runtime): `npx -y @nanonets/graft check` then `npx -y @nanonets/graft build` on drift.

Health smoke: `GET http://localhost:8000/api/health` → `{ "status": "ok", "service": "goat" }`.

## Stack

Matches `.cursor/rules/deployment-standard.mdc`: frontend Vite/React on **Vercel**, API FastAPI on **Render**, DB/auth **Supabase**, DNS Cloudflare. Local loop without Docker: Postgres `goat` on `localhost:5432` (or Supabase Cloud) + backend `:8000` + frontend `:3000`. Prod: `goat.fmazurkiewicz.dev` / `api-goat.fmazurkiewicz.dev`. Cold-start UX is ADR-19 wake-window lamp, not a keep-alive pulse.

## Learned User Preferences

- Setup, migration and deploy instructions should be concrete, step by step, with key→value tables — not general descriptions.
- Deploy/prod: cloud (Supabase + Render + Vercel + Cloudflare); locally: backend + frontend + Postgres on localhost (database `goat`); local auth is email/password (dev), on Render/production only OAuth.
- For larger topics (architecture, plan, audit) prefer parallel review by a team of experts (subagents) and a concise synthesis of decisions.
- After larger chunks of work, often asks to update documentation and push to `main` (after tests, when asked).
- Agent communication and responses: in English (overrides conflicting Polish user rules). Code comments, docstrings, JSDoc, SQL comments, Cursor rules, and docs: English; user-facing UI strings, validation messages, and SSE/chat copy stay Polish.
- Do not paste real secrets into `.env.example`, commits or chat — only placeholders.
- Selecting a ready-made persona: dropdown list (`Select`), not a grid of buttons/radio.
- Click on the "Coach" brand/name in navigation returns to the chat screen; nickname and logout (Wyloguj) in account settings (`/settings`, not in the header); **Profile** tab (`/profile`) — biometrics and notes from `user_profile` (preview + manual editing; Goat and personas also save from chat).
- Default/seed results must depend on the user's personas, not on universal hardcoded sports (e.g. badminton/triathlon for everyone).
- Deleting a persona: from the edit dialog (not only from the card on the list).
- In chat (General conversation): the user communicates **only with Goat**; directly with a persona only via `/slug`; Goat consults experts with the `consult_persona` tool (roster = the user's active personas, including custom ones) — **rarely**, only when an expert is really needed (Goat handles simple things himself); roundtable → N consults + **one** Goat bubble; status "Goat is consulting with {persona}…"; ability to stop generation; Markdown (`remark-gfm`/`remark-breaks`, preamble v7); dedup label when name=role; tool chips instead of JSON; Send field in viewport; conversation titles auto + edit via right-click.
- Personas should compose plans and save results (Plan/Results tabs); plan agreed with all active personas **with Goat's involvement (harmonization of contributions)**; Goat must be able to modify any plan; in the Plan, preview of each persona's contribution and the final effect; day blocks expanded in-place (week and month), not a side panel; generation with progress and ability to cancel.

## Learned Workspace Facts

- Repo / product is named **`goat`** (not `coach-dev`); the app is a Multi-Persona Coaching App (max 5 personas, chat, results, plans).
- Stack: frontend Vite + React (Vercel), backend FastAPI (Render), Supabase Cloud (Postgres + Auth), OpenRouter, Cloudflare DNS.
- Monorepo: `backend/`, `frontend/`, `supabase/migrations/`, docs in `docs/` (`cloud-setup.md` = current deploy).
- Cloud migrations: SQL Editor — re-init: `supabase/reset_public.sql` → `0001_init.sql` → `0002_exercise_catalog.sql` (without 0003; safety in `app_private`); running under motor skills: `0007_running_metrics_strength.sql`; role boundaries: `0009_persona_role_boundaries.sql`; drop `chat_model`: `0010_drop_personas_chat_model.sql`; multi-slash invoked_via: `0011_invoked_via_multi_slash.sql`; catalog: `0012_exercise_catalog_source_nullable.sql` + `0013_exercise_catalog_seed_free_exercise_db.sql` (photo_path relative); dual photos: `0014_exercise_photo_path_2.sql`; approval gate: `0015_user_approval_gate.sql`.
- **Goat (Team Lead):** in `general` session without `/slug` — Goat exclusively (`persona_id=null`); expert via `consult_persona` (backstage; rarely); directly with a persona only via `/slug`; for plan — `rebuild_plan` (+ `user_brief`); stage 3 = Goat harmonizes (final voice); in chat Goat `upsert_plan_items` on any active persona; docs: `docs/technical/team-lead.md`, ADR-17.
- `motor_coach` → results category `strength` (UI: Training tab); without a separate `running`/`cardio` category.
- Persona prompt: user edits only behavior (`system_prompt`); doctor/medications/red flags in `app_private.persona_template_safety` + preamble; in chat prompt, today's date (Europe/Warsaw); one OpenRouter model for chat/persona/planner (`OPENROUTER_CHAT_MODEL`, Grok by default); `OPENROUTER_PLANNER_MODEL` empty = same as chat; not a column in DB (`0010_drop_personas_chat_model.sql`).
- Hosting: domains `goat.fmazurkiewicz.dev` (FE), `api-goat.fmazurkiewicz.dev` (API); prod Supabase `dynkfllyfykudfxymmtc`; Vercel SPA `frontend/vercel.json` rewrite `/(.*) → /index.html`; Cloudflare CNAME `goat` / `api-goat`: DNS only (grey cloud), Name/Target without `https://`.
- On Render `DATABASE_URL` must go through Supabase Connection pooler (Supavisor, port 6543); direct `db.<ref>.supabase.co` gives `Network is unreachable` (IPv6); locally: `postgresql+asyncpg://…@localhost:5432/goat` (without pooler).
- Sole admin: `fmazurkiewicz@gmail.com` (allowlist); `/account` = nickname (ADR-15), `/profile` = `user_profile` (ADR-11, biometrics/notes); admin panel: Moderation and Audit log in collapsed "Platform diagnostics"; `ProfilesRepo.ensure()` before write; asyncpg: UUID→str in DTO, jsonb via `CAST(:param AS jsonb)`.
- **User approval (ADR-22):** public signup; new `profiles.is_approved=false` except admin email on INSERT only; waiting screen + 15s poll of `GET /account`; feature APIs 403 `account_pending_approval`; admin Accept/Revoke; no self-revoke; grandfather existing rows true. Migration `0015_user_approval_gate.sql`.
- Chat tools: `log_result` (trainers = own UUID; **also Goat — `source_persona_id=NULL`**, ADR-6 amendment 2026-08-17), `update_user_profile` (trainers **and Goat**), `get_plan`, `upsert_plan_items` (trainers = their own; **Goat = any active persona**); **`rebuild_plan` and `consult_persona` only Goat**; plan progress: Goat row during harmonization; `GET /plans?start_date&end_date` → `{plan, items}`; `POST /plans/generate` returns `job_id`; polling job by `personas`; preamble v7; SSE statuses PL; layout: AppShell `h-svh`/`h-dvh`, scroll in MessageList.
- **Mobile `/chat` (2026-08-17):** entry without `:sessionId` → auto-jump to newest conversation (`latestSessionId`, `useRef` one-shot guard); return to `/chat` → `ChatSessionsScreen` (full-screen list, without `Sheet`); desktop unchanged.
- **Cold-start lamp (ADR-19):** next to "Coach" only when API does not respond ≥ 2 s; hover/tap "Waking up the app…"; after 200 it disappears; `/api/health` only in the wake-up window (not keep-alive) — Render Free may sleep.
- **Exercise catalog (2026-08-23/24):** import [yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db) (**Unlicense**) into ADR-14 `exercises` — 868 PL entries (LLM translation in seed). Migrations `0012` + `0013` (generated seed). Scripts: `scripts/import_free_exercise_db.py` (`--upload-photos` both `0.jpg`+`1.jpg`, `--skip-sql`), `scripts/download_free_exercise_db_photos.py` (disk), and `scripts/translate_exercises.py`. UI: `/exercises/:slug` (both photos), clickable names in plans, category Select; idle = **3 random** exercises until explicit **Search** (`query` ≠ `searchTerm`; **"Show other"** re-rolls) — `lib/exercise-catalog.ts`, `ExerciseSearchBar.tsx` + `ExerciseCatalog.tsx`. **Photos:** prod bucket `exercise-photos` stores objects at `exercise/free-exercise-db/<Id>/{0,1}.jpg`; DB `photo_path` / `photo_path_2` stay relative `free-exercise-db/<Id>/…`; API/FE prefix via `PHOTO_STORAGE_ROOT=exercise` / `bucket_object_path()` / `exercisePhotoSrc()`. `GET /exercises`: coerce `id` UUID→str in DTO (asyncpg pattern). Conscious skip of hasaneyldrm/openGym — AGPL/© Gym visual do not enter goat.
- **Consultation visibility (2026-08-22, merged to main via PR #1):** user can expand under a Goat message "{persona} replied" — question + answer from `consult_persona`; live = SSE `consult_detail`, history = pairing `tool_calls`↔`role='tool'` by `tool_call_id` in `visibleChatMessages`; hotfix d9cd599: `ChatMessageOut` must expose the `tool_calls` field in `GET /chat/sessions/{id}/messages` (without it the panel did not render from history) + contract test `backend/tests/test_chat_messages_contract.py`; ADR-17 untouched; spec `docs/superpowers/specs/2026-08-22-goat-consult-transparency-design.md`.
- **Pull-to-refresh (2026-08-22, merged to main via PR #1):** mobile touch-only, all screens (`PullToRefresh` in AppShell around `<Outlet />`), threshold 72 px, soft refresh `invalidateQueries()`; `overscroll-behavior-y: none` on html/body; spec `docs/superpowers/specs/2026-08-22-pull-to-refresh-design.md`.
- **Graft (ADR-20, 2026-08-23):** local code map for the agent (structural `graft build`, $0); `graft/` in `.gitignore` and `.cursorignore`; only Cursor wiring is committed; `graft build` after merge / large refactor / drift (`graft check`); setup: `docs/technical/local-setup.md` §G. Repo rule: `.cursor/rules/graft.mdc`.
