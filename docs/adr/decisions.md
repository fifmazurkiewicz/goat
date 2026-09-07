# Architecture Decision Log (ADR)

## ADR-1: Plan generation — without a separate worker on Render

**Status:** accepted (confirmed by the user).

**Context:** weekly/monthly plan generation is potentially a long-running operation (tens of seconds to several minutes). Render has no free tier for Background Workers (min. Starter $7/month).

**Decision:** execution in the same process as the API (FastAPI `BackgroundTasks`), wrapped in durable `plan_generation_jobs`/`plan_generation_job_personas` tables (not just a `plans.status` column) — gives visibility, per-persona retry and partial-success at no cost of a second service.

**Consequences:** requires a reaper on app startup (jobs hung after restart → `error`) and making sure heavy/blocking operations do not freeze active SSE streams in the same process (`asyncio.to_thread` for sync fragments).

**Migration threshold:** when generation time starts approaching several minutes or RAM/CPU load starts impacting chat responsiveness → split out a separate Render Background Worker consuming the same `jobs` table as a queue (`SELECT ... FOR UPDATE SKIP LOCKED`). The database schema already supports this without changes.

---

## ADR-2: Plan generation — three stages, priority: synchronization between personas

**Status:** accepted.

**Context:** a single mega-prompt with all personas at once risks cutting off JSON (20–45k output tokens for 5 personas/month) and "diluting" quality for later personas in the queue. At the same time, the product priority is plan consistency between personas (diet matching training, regeneration), not just the quality of a single persona in isolation.

**Decision:** 3-stage pipeline — (1) coordinator pass (cheap model, shared skeleton), (2) per-persona generation in parallel (`PLANNER_MODEL`, `asyncio.gather`), (3) harmonization ("calendar steward" — full review, targeted patches for conflicts).

**Consequences:** an additional LLM call (stage 3) increases generation cost by about one planner call, but addresses the synchronization requirement explicitly, instead of counting on the model to provide that on its own in isolated per-persona calls.

---

## ADR-3: RLS as a real barrier — backend connects as the authenticated user

**Status:** accepted.

**Context:** a backend connected by default through `service_role` would invalidate RLS as a protection mechanism — any bug in the code would become a potential data leak between users.

**Decision:** backend connects per-request as the authenticated user (`SET LOCAL` + `set_config('request.jwt.claims', ...)` from JWT, within a single transaction). `service_role` only for Supabase Admin API and `/admin/*`, with explicit in-code verification of `profiles.is_admin`.

**Consequences:** requires `NullPool` + `statement_cache_size=0` in `asyncpg` (Supavisor transaction mode compatibility) and a mandatory RLS contract test in CI.

---

## ADR-4: Three layers of defense against jailbreak/abuse

**Status:** accepted.

**Context:** personas are editable and shareable between users — a two-layer safeguard (preamble + moderation on creation) protects only the `system_prompt` at creation time, it does not protect against a jailbreak entered as a message during conversation.

**Decision:** add layer C — runtime guard (heuristics + sampled classifier) on every chat message, plus re-moderation on **every** persona edit (not only creation), plus `preamble_version` to force re-check after a platform preamble change.

**Consequences:** additional cost (heuristics cheap, classifier only on hit) and `moderation_events` table with retention/RBAC requirements due to potentially sensitive content (GDPR).

---

## ADR-5: Authentication — Google OAuth only, no magic link

**Status:** accepted (confirmed by the user).

**Context:** the original spec assumed magic link + Google OAuth.

**Decision:** Google OAuth only via Supabase Auth. Simplifies the login UI and removes the need to handle transactional emails at the start.

**Consequences:** no login fallback for users without a Google account — acceptable at the scale of 2–5 known users.

---

## ADR-6: `log_result` as a batch tool, not a single entry

**Status:** accepted.

**Context:** relying on the model batching multiple `log_result` calls in one round is not guaranteed behavior — models often call tools sequentially.

**Decision:** `log_result(entries: list[...])` accepting 1-N entries in a single call, with validation and per-entry result (partial success possible).

**Consequences:** the tool-calling round limit (3–5) becomes a pure safeguard against loops, not a real restriction of the normal path (e.g. logging a whole workout).

**Amendment 2026-08-17:** `log_result` is also given to **Goat** (previously trainers only). In the `general` session the user reports the result to the team lead, and after limiting `consult_persona` to rare cases there was no one to save it. Goat's entries go with `source_persona_id=NULL` (the sentinel `__team_lead__` is not a record in `personas`, the column has an FK). Spec: [2026-08-17-mobile-history-and-goat-log-result-design.md](../superpowers/specs/2026-08-17-mobile-history-and-goat-log-result-design.md).

---

## ADR-7: No chat rolling summary in MVP

**Status:** accepted.

**Context:** a rolling summary (LLM summarization of older history) requires a separate async pipeline, introduces non-determinism and is justified only with realistically long conversations.

**Decision:** start with just a sliding window of the last M messages. Rolling summary added later, data-driven, when production shows real cutting of important context.

**Consequences:** with very long chat sessions the older context will be lost without a summary — acceptable risk at the start.

---

## ADR-8: "Min. 1 active persona" route guard — deferred

**Status:** accepted (confirmed by the user).

**Decision:** the guard blocking `/chat`/`/plans` without an active persona is implemented after the core flow (personas → chat → results → plan) works end-to-end, not as a blocker for the first iteration.

---

## ADR-9: Adherence tracking and charts in `/results` — in MVP scope

**Status:** accepted (confirmed by the user).

**Decision:** `/plans` day panel shows "Planned" (plan_item) next to "Completed" (results from that day) as a simple juxtaposition, without complex analytics. `/results` gets trend charts per metric (`recharts`/shadcn `Chart`) — without schema changes, only an index `results_user_category_metric_date`.

---

## ADR-10: Weekly recap and external integrations — out of scope

**Status:** accepted (confirmed by the user).

**Decision:** weekly recap from a persona — not entering MVP, not even planned as post-MVP. Garmin/Strava/Apple Health import/sync — "maybe someday", with no impact on the architecture now.

---

## ADR-11: User profile (biometrics) — shared table, filled conversationally via tool call

**Status:** accepted (confirmed by the user, added before cloud deployment).

**Context:** without biometric data (weight, height, age, activity level, goal) the generated training/diet cannot be really personalized. Requirement: the persona should "ask" the user for these data during configuration, not require filling out a form up-front.

**Decision:** a shared, one-per-user `user_profile` table (not per-persona — biometric data is shared regardless of which persona the user talks to; distinguish from `personas.persona_constraints`, which is specific to a given persona and **not accessible to the end-user** in the API/UI — see `ai-pipeline.md`). Filled via a new `update_user_profile` tool (same class as `log_result` — validation, partial update, error returned to the model as tool response), available to every persona. `ContextBuilder` detects an incomplete profile and appends a dynamic instruction "ask naturally about missing data" to the prompt — disappears automatically when the profile is filled. `/profile` form as a fallback for users who prefer to enter data directly.

**Consequences:** `PlanOrchestrator` (stages 1-2) gets `user_profile` alongside `persona_constraints` as additional personalization context. Lack of a complete profile does not block plan generation (consistent with ADR-8 — no new hard blocks in MVP), the planner receives information about gaps and can note that in the plan's notes.

---

## ADR-12: Active persona limit — per account, admin-editable (not a global constant)

**Status:** accepted.

**Context:** the limit of 5 active personas per user was a hard-coded constant (DB trigger `enforce_persona_limit` + `PersonaService.MAX_ACTIVE_PERSONAS`). With 2–5 users (Vercel Hobby) the admin wants to be able to give a chosen user more (or less) than the default 5, without a code change/deploy.

**Decision:** new column `profiles.max_active_personas` (default 5, `CHECK` 0-50) — one value per account, persistent regardless of billing period (intentionally NOT in `usage_limits`, whose PK `(user_id, period_start)` resets monthly — wrong place for a persistent setting). Trigger `enforce_persona_limit` reads the value from `profiles` instead of the hardcoded `5`; `PersonaService.assert_can_activate_persona` in the backend does the same via `ProfilesRepo`, producing a readable 409 message before hitting the DB. Admin edits via `PATCH /api/v1/admin/users/{user_id}/persona-limit`, saved in `admin_audit_log` (`action='edit_persona_limit'`) like any other admin action.

**Consequences:** the DB trigger remains the last line of defense (consistent even with buggy/skipped API validation), the backend is only a faster, cleaner layer in front of it — same pattern as the original "5" limit. Requires `ProfilesRepo` (nonexistent until now, also blocking `require_admin`) — added in the same change.

---

## ADR-13: "General conversation" (auto-routing) + persona invocation via `/slug`

**Status:** accepted (confirmed by the user, based on `Coach App - Makiety.dc.html` mockups).

**Context:** the mockup introduces a chat mode not assigned to a single persona ("General conversation"), where the user asks a question without picking a specific trainer and the system decides who answers — and an explicit persona invocation mechanism via `/{slug} message content`. The current model (`chat_sessions.persona_id NOT NULL`, 1 persona/session, no per-message persona attribution) physically doesn't support this. The original mockup showed TWO personas answering one message in a row — the team (architectural audit + UX) recommended simplifying to one persona per turn due to the risk of user disorientation (contradictory advice, unclear "who am I talking to") and cost; the user confirmed this direction.

**Decision:**

- `chat_sessions.persona_id` nullable + `session_type` (`'persona'` | `'general'`) — `general` session has `persona_id = NULL` (schema consolidated in `0001_init.sql` — see note at the top of that migration file: the project hadn't been deployed yet, so the history of incremental ALTERs from early iterations was merged into a single base migration instead of being kept separate).
- `chat_messages.persona_id` (per-message attribution — in a `general` session different `assistant` messages can come from different personas) + `chat_messages.invoked_via` (`'auto_routed'` | `'slash_command'`).
- `personas.slug`, unique per user, generated from `type + name` on creation and **regenerated on name change** (collisions resolved by numeric suffix in `PersonaService`).
- **Routing — one or many personas sequentially per user turn** (max 3 for auto-routing), chosen by a lightweight "conversation manager": (1) parsing one or many `/slug` at the start of the message (order = order of responses, `invoked_via='multi_slash'` when ≥2); (2) lacking slashes — classifier returns `persona_ids[]` (1..N when the question touches ≥2 roles); (3) each selected persona answers through the EXISTING `ChatOrchestrator.handle_message` sequentially — many `persona_turn_start`, **one** `done` at the end.
- **Fallback on uncertain/no classifier hit:** the persona that most recently answered in this `general` session (context continuation); if this is the first message of the session without previous history — the user's first active persona (deterministic, without an additional clarifying question in MVP).
- `ContextBuilder` when building the system prompt for persona X in a `general` session filters history: all `role='user'` (shared) + `role in ('assistant','tool')` WHERE `persona_id = X` — otherwise persona X would "see" other personas' answers in history as its own.
- SSE contract (`architecture.md` §3) extended with `persona_id`/`persona_label` in events and an event `persona_turn_start {persona_id, persona_label}` before each persona's tokens.
- Frontend: chat input in a `general` session has autocomplete on typing `/`; on multi-reply it finalizes the previous answer to the history cache before the next `persona_turn_start`.
- Plan tools in chat: `get_plan`, `upsert_plan_items`, `rebuild_plan` (full 1–3 pipeline).

**Consequences:** multi-persona increases cost/latency (N LLM calls) versus the original simplification "1 persona"; the limit of 3 and sequentiality protect UX and budget. Requires stream statuses (Phase 1) and updates to `frontend.md` / `ai-pipeline.md`.

---

## ADR-14: Exercise catalog — new domain of reference content

**Status:** accepted (confirmed by the user).

**Context:** the mockup (Settings tab, `catalogExercisesAll`) shows a searchable gallery of exercises (categories, difficulty level, execution description, common mistakes, photo), linked to the persona type (motor coach / badminton coach). This is a completely absent domain in the current database schema.

**Decision:** new `exercises` table (migration `0002_exercise_catalog.sql`) — static reference content, seeded by migration (analogously to `persona_templates`/`plan_templates`), without a separate domain service (no business logic beyond filtering — a thin router + repository suffice). Categories as `text[]` (small, known list, no separate dictionary table). One endpoint `GET /exercises` returning full objects (catalog of a few dozen entries — no pagination/detail-fetch needed). Photos in Supabase Storage (public bucket `exercise-photos`), added manually during seeding — no upload endpoint in MVP. **Catalog stays in the Settings tab** (per mockup — user consciously kept this placement despite the alternative proposed in the UX audit, i.e. a separate route linked from `/plans`/persona configuration).

**Consequences:** SELECT RLS public for `authenticated`, no INSERT/UPDATE/DELETE for a regular user (content managed only by migrations/seed, like the rest of the "ready-made" items). Editability by admin/user — consciously deferred, requires a separate decision when that need arises.

**Amendment (2026-08-23, free-exercise-db import):** catalog scale grows from 5 to ~873 entries ([yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db), license **Unlicense** — public domain, no attribution; earlier idea of hasaneyldrm/openGym rejected on license grounds). Changes from the original decision:

- `common_mistakes` **nullable** (migration `0012`) — the dataset doesn't contain this content; we don't fabricate technical advice. Manually curated entries keep their value.
- New column **`source`** (`'manual'` | `'free_exercise_db'`) — provenance + protection of manual entries on re-imports (`ON CONFLICT (slug) DO NOTHING` will never overwrite them).
- Import = **script-generator** (`scripts/import_free_exercise_db.py`) → generated seed `0013_*.sql` in the repo (not "added manually during seeding" and not INSERT directly into the DB — the artifact in git is the only truth, works locally and on cloud via SQL Editor). Photos (**both** frames `0.jpg` + `1.jpg`) are uploaded by the same script to the `exercise-photos` bucket (service role from env, without supabase-py); local cache via `scripts/download_free_exercise_db_photos.py`. `photo_path_2` added in `0014`. Re-import: `DELETE WHERE source='free_exercise_db'` + rerun.
- **Conscious EN/PL duplicates:** manual PL entries `przysiad-ze-sztanga` / `wyciskanie-sztangi-lezac` / `martwy-ciag` **removed** in `0012` (user's decision) — the EN counterparts from the dataset stay. `badminton_coach` entries untouched (not covered by the dataset).
- Imported content **in Polish** (amendment 2026-08-23, user's decision): name + short description + execution steps translated via LLM **when generating the seed** (offline, cache in `.tmp/`, script `scripts/translate_exercises.py` via OpenRouter) — zero LLM calls in runtime; the EN original stays in `name_en` (matches clickable links from plans). Category filter in UI: Select with grouping (not chips). Exercise detail: shared page `/exercises/:slug` (dialog removed), also clickable from plan tables via `lib/exercise-matcher.ts`. The scale of ~870 entries doesn't require pagination: `loading="lazy"` on `<img>`, gzip on the API, client-side filter with `useDeferredValue`.
- The assumption "catalog of a few dozen entries — no pagination/detail-fetch needed" stops being true at scale, but the decision to skip pagination is confirmed (lazy images + gzip; split list/detail deferred until a real problem appears).

---

## ADR-15: `/settings` — account settings (nickname, theme) as a new route

**Status:** accepted (confirmed by the user).

**Context:** the mockup introduces a Settings tab with nickname editing and light/dark theme toggle, missing from `frontend.md` §1 (routing) and from `profiles`.

**Decision:** new column `profiles.nick` (nullable, fallback to name from Google OAuth — schema consolidated in `0001_init.sql`), new separate endpoint `GET/PATCH /api/v1/account` (intentionally NOT an extension of `/api/v1/profile`, reserved for user biometrics — ADR-11, different responsibility). Light/dark theme: **without DB persistence** — purely `localStorage` on the frontend; with the scale of a few known users and typically one device, cross-device synchronization doesn't justify an API round-trip. Exercise catalog (ADR-14) shares this page in the UI but remains an independent API domain.

**Consequences:** new route `/settings` (protected, auth) in `frontend.md` §1. If the theme should be persistent across devices in the future — trivial addition of `profiles.theme` without impacting the rest of the architecture. Logout (2026-09-07) lives on the same account card, not in the shell nav: `signOut` already existed in `useAuthStore` / `lib/supabase` with no UI.

---

## ADR-16: Usage limit as USD budget per account (not Free/Pro plans)

**Status:** accepted (confirmed by the user).

**Context:** the admin panel mockup showed usage as a dollar amount with a plan label ("Free"/"Pro" — `$4.20 / $10.00`), suggesting paid subscription plans absent everywhere else in the spec (MVP is supposed to be non-commercial, `usage_limits` previously tracked only counts: messages, tokens, plan generations). User clarified: the dollar amount should be a **real, enforced protective budget against excessive API usage** (not a billing/subscription mechanism) — default $10 per account, admin-editable. "Free"/"Pro" plan labels from the mockup rejected as misleading (suggesting a subscription that doesn't exist).

**Decision:** new column `profiles.usage_budget_usd` (default `10.00`, `CHECK` 0-1000) — pattern identical to `profiles.max_active_personas` (ADR-12): one row per account, persistent regardless of billing period, admin-editable (`PATCH /api/v1/admin/users/{user_id}/usage-budget`, saved in `admin_audit_log` like any other admin action). New column `usage_limits.cost_usd_used` — actual cost used in the current period, counted from OpenRouter responses (`prompt_tokens`/`completion_tokens` × model pricing, fetched and cached from `/api/v1/models` OpenRouter — not hardcoded). `UsageLimitService.check_and_increment_message` rejects (429) when `cost_usd_used + estimated_turn_cost > usage_budget_usd`, analogously to the existing counter mechanism. Column `usage_limits.tier` (unused plans concept) removed.

**Consequences:** admin panel shows `cost_usd_used`/`usage_budget_usd` (amount + editable limit), WITHOUT "Free"/"Pro" labels. Requires extending `ai-pipeline.md` with how cost is counted from OpenRouter pricing and maintaining the model price cache.

---

## ADR-17: Team Lead (Goat) — coordination of `general` sessions

**Status:** accepted (implemented 2026-08-04; **amended 2026-08-16**, delta 2026-08-17).

**Context:** In the `general` session (ADR-13) the routing classifier chose personas, but each answered in isolation — without a lead's brief. Then (2026-08-04) Goat relayed trainer quotes (`format_goat_relay`) — the "the dietitian is speaking" feeling on a motor skills question. The user expects a conversation **with the team lead**; experts only at Goat's request or via `/slug`.

**Decision:**

- **Goat** — system role (`TeamLeadSpeaker`, prompt in code). Not a user's persona in DB.
- **Visibility (2026-08-16):** In `general` without slashes **one turn** of `TeamLeadSpeaker` (`persona_id=null`). Specialist: tool **`consult_persona`** (slug from the active personas roster **of this user** — including `custom`; backstage, without a visible trainer message). UX status: `Goat is consulting with {label}…`. Roundtable = N consults + **one** Goat bubble.
- **Exception:** `/slug` / multi-slash / `persona` session — the user sees the persona directly; Goat doesn't start.
- **Plan:** Goat calls `rebuild_plan` in its turn (without a separate trainer loop as speakers). Optional `user_brief` (e.g. "no badminton") goes to the generation job; roles excluded by the brief don't generate items. Stage 3 = **Goat** (final voice: update/delete patches).
- **Tools:** Goat — `get_plan`, `rebuild_plan`, `update_user_profile`, `consult_persona` (max 5/turn; **default without consult**), **`upsert_plan_items`** (any active persona); trainers — the rest **without** `rebuild_plan` and `consult_persona`.
- **Role boundaries:** `[ROLE SCOPE]` (`persona_scope.py`) + safety overlay (migration `0009`).
- **Context:** `ContextBuilder` appends `[TRAINING PLAN]` and `[USER RECENT RESULTS]`.
- **SSE:** `persona_status` / `tool_result` for consult with Goat label; `persona_id: null`.
- **Background turn:** `chat_sessions.turn_in_progress`; FE: `useChatTurnRunner` in AppShell. Initial status: "Goat is preparing a response…" (not "agreeing with the team"). Plan progress: row `Goat · Team Lead` during harmonization.

**Consequences:** 0..N additional LLM calls only when Goat calls `consult_persona` (not always +1 JSON classifier). ADR-13 remains the source of truth for the session model and `/slug`. Documentation: `docs/technical/team-lead.md`. Spec: `docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md`.

**Supersedes (2026-08-16):** `format_goat_relay`, `TeamLeadService.plan_consultation` as speaker selection, bypass "1 active persona = that persona's turn", "invisible lead" design.

---

## ADR-18: Mobile viewport — `dvh` + visualViewport, no page-scroll on chat

**Status:** accepted (2026-08-16).

**Context:** On Android/iOS phones the chat history wasn't immediately visible. `h-svh` + `main overflow-y-auto` + three levels of `overflow-hidden` ate `MessageList`'s height. Virtualization (`estimateSize: 88`) and `scrollToIndex` in `useEffect` started from the wrong offset. Lack of `viewport-fit=cover` and `env(safe-area-inset-*)`.

**Decision:**

- Shell: `h-dvh` + CSS var `--app-height` from `window.visualViewport` (keyboard shrinks layout).
- On `/chat` and `/chat/:id` `main` = `overflow-hidden flex flex-col`; other routes stay `overflow-y-auto`.
- History: anchor at the bottom (`scrollIntoView`), without virtualization in MVP.
- Composer and pages: safe area; touch target ≥44px.
- Bottom nav (Chat / Plan / Results) — deferred; not polishing a 6-link bar as "target" IA on phones.

**Consequences:** chat doesn't scroll the whole page; other screens scroll in `main`. Bottom nav is a separate IA change (next sprint).

---

## ADR-19: API cold-start lamp — only when the backend doesn't respond

**Status:** accepted (2026-08-16).

**Context:** Render Free sleeps the Web Service after ~15 min. The SPA on Vercel is immediately available, so the first API requests hang for 30–60 s. The user refreshes the page because they don't know it's a cold start, not an outage.

**Decision:** frontend calls `GET /api/health` **only in the wake-up window** (AppShell mount or a network error on a real request). Lamp **only** when 200 doesn't come back within ≥ 2 s. Hover/tap: "Waking up the application, please wait." After 200 — stop probing, lamp disappears, TanStack Query refetches. After ~90 s without 200 — red and stop automatic (tap = one new window). Background tab and `/login` alone **don't** ping. No green lamp, banner, overlay, `refetchInterval`, or keep-alive — Render must be able to fall asleep after 15 min.

**Consequences:** the probe is not a heartbeat. Locally the lamp doesn't appear. Spec: `docs/superpowers/specs/2026-08-16-api-status-lamp-design.md`.

---

## ADR-20: Graft as local code map for the agent (not runtime)

**Status:** accepted (2026-08-23).

**Context:** every new agent conversation starts cold and pays the cost of repo exploration (grep, opening files). [Graft](https://github.com/nanonets/graft) builds a local graph once (tree-sitter, no LLM) and serves it to the agent via CLI / MCP.

**Decision:**

- Graft is **developer tooling** — zero impact on backend, frontend, Supabase, Vercel, Render, CI.
- Default **structural** layer (`graft build`, $0, no key). `--deep` (LLM) only consciously, key only locally.
- Graph `graft/` = local cache like `node_modules` — **in `.gitignore`**, never in a commit. Teammate / new machine: `graft build`.
- Only Cursor wiring is committed: `.cursor/rules/graft.mdc`, `.cursor/mcp.json`.
- Telemetry disabled (`graft telemetry disable`).
- `graft build` periodically: at session start on drift (`graft check`), after merge / large refactor, when `ask`/`callers` results look stale — not after every line.
- Global rule (all repos, greenfield and brownfield): `~/.cursor/rules/graft.mdc`.

**Consequences:** a new Cursor session requires a restart to load MCP. Step-by-step setup: [`local-setup.md`](../technical/local-setup.md) §G.

---

## ADR-21: Agent runtime hardening — cancel, consults, confirm, usage

**Status:** accepted (2026-09-06).

**Context:** Render Free kills the process; plan `_run` could still finish as `success` after cancel; chat turns with consults exceeded the 90s SSE deadline; nested consults could write results/profile/plan; `rebuild_plan` silently enqueued a full 3-stage job; usage reconcile recomputed the reserve with `prompt_chars_estimate=0` (double-count); Goat had no template-safety overlay.

**Decision:**

- Keep ADR-17: the user hears only Goat. No Agno Team / A2A / keep-alive. Do not parallelize `consult_persona`.
- Plan cancel registers an in-process Task (`job_registry`, same as `turn_registry`) and `_run` refuses to finalize `success` unless the job is still `pending|running`.
- Startup **requeues** all `pending|running` background jobs first, then orphans without an active bg row; clears orphaned `turn_in_progress`.
- Nested consult tools = `get_plan` only; consult cap increments after success.
- `rebuild_plan` requires a prior `needs_confirm` plus the user’s next-turn „tak” (model `confirmed` is ignored) or reuses an in-flight `job_id`.
- Plan job status writes are CAS on `pending|running`. Chat `retry` is 409 while a live in-process turn exists.
- Reconcile chat (and plan jobs after completion) with the **reserved** USD, not a zero-prompt recompute.
- Goat gets `TEAM_LEAD_SAFETY_OVERLAY` (red flags / no meds), same family as trainer templates.

**Consequences:** a Goat turn with consults can last up to ~210s; a full plan rebuild is never silent. Docs: `docs/technical/team-lead.md`.

---

## ADR-22: Manual user approval gate

**Status:** accepted (2026-09-07).

**Context:** Public signup stays (Google OAuth / local dev login). The product is still a small allowlist of real users. Without a gate, anyone who can complete OAuth gets personas, chat, and plans.

**Decision:**

- `profiles.is_approved` boolean. Existing rows grandfathered `true`. New inserts default `false`.
- Auto-approve **only** on `ProfilesRepo.ensure` INSERT (and the matching `handle_new_user` trigger) for `fmazurkiewicz@gmail.com` plus any extra `ADMIN_EMAILS`. Subsequent `ensure`/`get` never flips the flag.
- Unapproved users may log in and see one waiting screen (poll `GET /account` every 15s). Logout works. No personas / plans / chat / admin chrome.
- Feature routers return 403 `account_pending_approval`. Health and GET `/account` stay ungated. Admin requires `is_approved` and `is_admin`. Admin cannot revoke themselves. Accept does not overwrite `usage_budget_usd`.
- No notification emails or Slack.

**Consequences:** a new signup is usable only after an admin clicks Accept. Revoke returns the same waiting screen. Cloud SQL: apply `supabase/migrations/0015_user_approval_gate.sql` in the SQL Editor before relying on the new column in production.

---

## ADR-23: In-repo agent constitution + health `service`

**Status:** accepted (2026-09-07).

**Context:** Global `~/.cursor/rules` applied constitution on this machine, but a clone of goat only had `.cursor/rules/graft.mdc`. `GET /api/health` omitted `service`. Frontend tests existed but CI ran only lint + build.

**Decision:**

- Commit the constitution rules in `.cursor/rules/` (plus `.cursorignore`, Taste dials overlay, Commands in `AGENTS.md` / nested `backend/` and `frontend/` AGENTS).
- Liveness JSON is `{ "status": "ok", "service": "goat" }`. Keep ADR-19 wake-window lamp; do **not** add a keep-alive `ApiPulse` poll (Render Free should still sleep).
- CI runs `npm test`, Dependabot, and TruffleHog `--only-verified`.

**Consequences:** agents on a fresh clone get the same process/stack/secrets rules. Env names live in [`../technical/configuration.md`](../technical/configuration.md).
