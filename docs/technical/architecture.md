# Architecture — Multi-Persona Coaching App

## 1. Overview

Monorepo: `backend/` (FastAPI, Render), `frontend/` (Vite+React, Vercel), `supabase/migrations/` (single source of truth for the schema).

```
coach-app/
├── backend/app/
│   ├── api/routers/      # personas, chat, results, plans, admin, health — THIN
│   ├── core/             # config, security (JWT+JWKS), middleware, rate_limit, exceptions
│   ├── domain/
│   │   ├── chat/         # ChatOrchestrator, ContextBuilder, routing.py (ChatRoutingService — ADR-13)
│   │   ├── plans/        # PlanOrchestrator (3-stage), jobs runner
│   │   ├── personas/     # PersonaService, resolve_persona_columns()
│   │   ├── moderation/   # ModerationService (classifier + runtime guard)
│   │   └── usage/        # UsageLimitService (atomic increment+check, USD budget — ADR-16)
│   ├── llm/
│   │   ├── openrouter_client.py   # transport (httpx)
│   │   ├── streaming.py           # OpenRouter SSE parser -> domain events
│   │   └── tool_calling.py        # accumulating tool_call fragments
│   ├── repositories/     # all SQL knowledge, the only place touching the DB
│   └── models/ / schemas/
├── frontend/src/
│   ├── pages/  ├── components/  ├── lib/  └── store/
├── supabase/migrations/
└── .github/workflows/
```

Rule: routers are thin (parsing + calling the orchestrator), all business logic lives in `domain/`, all SQL knowledge in `repositories/`. Domain services are plain Python classes (Protocol for dependencies) — they don't know FastAPI, so they can be tested without a database/HTTP.

## 2. Database — access and RLS

**SQLAlchemy 2.0 Core** (not full ORM) + `asyncpg` — migrations go on a separate path (Supabase CLI, raw SQL), so ORM-based relation/migration mapping would be duplicating the system.

**RLS through Supavisor (transaction mode) — the specific pattern:**

- `NullPool` in `create_async_engine` — pooling is done by Supavisor, we don't duplicate it in the app.
- `connect_args={"statement_cache_size": 0}` — **mandatory**. `asyncpg` caches prepared statements client-side by default; in transaction mode Supavisor assigns a different physical connection to each transaction, so a statement prepared on one backend doesn't exist on the next (`prepared statement does not exist`).
- `SET LOCAL` (never `SET`) + `set_config('request.jwt.claims', json, true)` — set in the same transaction as the queries, auto-undone on `COMMIT`/`ROLLBACK`. Session `SET` would leak between users with a shared physical connection.
- `service_role` — separate engine/DSN, used **exclusively** for Supabase Admin API and `/admin/*`, never as a fallback default dependency. `/admin/*` endpoints have explicit, in-code verification of `profiles.is_admin` — hiding in the UI is not authorization.
- Claim format must be consistent with what RLS policies in SQL migrations expect (typically `auth.uid()` reads `request.jwt.claims->>'sub'`) — this is a shared contract between SQL and backend code, documented in [`database-schema.md`](database-schema.md).

## 3. Chat — SSE + multi-turn tool calling

The backend is an **active aggregator**, not a 1:1 SSE tunnel from OpenRouter to the frontend.

**Implementation:** `sse-starlette` (`EventSourceResponse`, built-in `ping=15` heartbeat — Render proxy breaks idle SSE connections, the heartbeat prevents it). Producer/consumer pattern via `asyncio.Queue`:

```python
async def chat_stream_endpoint(request: Request, ...):
    queue: asyncio.Queue[dict] = asyncio.Queue()
    orchestrator_task = asyncio.create_task(run_chat_orchestrator(ctx, queue))

    async def event_generator():
        try:
            deadline = asyncio.get_event_loop().time() + settings.chat_hard_timeout_s
            while True:
                if await request.is_disconnected():
                    orchestrator_task.cancel()
                    break
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    orchestrator_task.cancel()
                    yield {"event": "error", "data": '{"code":"timeout"}'}
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=min(15, remaining))
                except asyncio.TimeoutError:
                    continue  # sse-starlette itself will send ping
                yield event
                if event["event"] in ("done", "error"):
                    break
        finally:
            if not orchestrator_task.done():
                orchestrator_task.cancel()

    return EventSourceResponse(event_generator(), ping=15)
```

**Orchestrator loop (`run_chat_orchestrator`):**

1. `httpx.AsyncClient.stream("POST", ..., tools=[log_result_schema])` to OpenRouter.
2. `delta.content` → `queue.put({"event": "token", ...})`.
3. `delta.tool_calls` (fragments: `id`+`name` in first chunk, `arguments` glued piece by piece) → accumulate in `dict[int, ToolCallBuffer]` keyed by `index`, until `finish_reason == "tool_calls"`.
4. Parsing JSON arguments + Pydantic validation (**untrusted input even though it comes from "our" model**) → execute `log_result` (batch, see [`ai-pipeline.md`](ai-pipeline.md)) → save to `results`.
5. Saving `assistant` message (with `tool_calls`) + `tool` message (with result) **in one transaction** — otherwise a crash between them leaves inconsistent history.
6. Next request to OpenRouter with full history → repeat until `finish_reason == "stop"` or **hard limit of 3-5 rounds** (protects against loops/cost).
7. `queue.put({"event": "tool_result", "data": {"tool_name", "summary", "success"}})` after each
   save — frontend shows an inline chip (not raw JSON tool response).

**Critical — the DB connection cannot live for the whole stream.** The chat endpoint does NOT take a long-lived DB dependency via `Depends`. The orchestrator opens short transactions only for the moment of save (per round), releasing the connection immediately — otherwise with a few parallel chats (60–90s each) the Supavisor pool exhausts quickly.

**Cancellation:** **Stop** button → `POST /chat/sessions/{id}/cancel` (`cancel_turn` in `turn_registry`) + `AbortController` on FE closes the SSE and cancels the in-process turn. Just disconnecting SSE (navigation away from chat) **does not** cancel the turn — generation continues in the background (`turn_in_progress=true`, no live client). A later `retry: true` is allowed only when the DB flag is set **and** there is no live in-process task (orphan after a process kill). A live turn always returns 409. The orchestrator must not catch `asyncio.CancelledError` with a broad `except Exception`.

**Frontend SSE events (contract):** `token`, `tool_call_start`, `tool_result`, `consult_detail` (2026-08-22, only Goat/`consult_persona` — payload `{tool_call_id, slug, persona_label, question, answer}`; FE renders expandable consultation preview under the Goat message), `done`, `error`, and `persona_turn_start` (see below) — defined as a shared JSON Schema/Pydantic model, so frontend and backend don't drift on field names.

### 3a. "General conversation" — Goat + `/slug` (ADR-13 / ADR-17)

Alongside the `persona` session (1:1) there is a `general` session (`session_type='general'`, `persona_id IS NULL`).

1. **Without slashes (2026-08-16):** one `TeamLeadSpeaker` turn — the user sees only Goat
   (`persona_id=null`). Expert: `consult_persona` tool (slug from the active personas roster
   **of this user**, including `custom`; nested `client_visible=false`, no visible trainer
   message). Status: `Goat is consulting with {label}…`. Cap 5 consults / turn.
2. **Slash / multi-slash:** `parse_multi_slash_command` — persona(s) directly; Goat does not
   start.
3. **Plan:** Goat calls `rebuild_plan` in its turn.
4. `ContextBuilder`: Goat — full `general` session history; trainer in consult — profile / plan /
   results context (1:1 history not required in v1).
5. `done` once at the end of the user's turn.

Details: `docs/technical/team-lead.md`. Spec: `docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md`.

Tools: Goat — `get_plan`, `rebuild_plan`, `update_user_profile`, `consult_persona`; trainers —
`get_plan`, `upsert_plan_items`, `log_result`, profile (**without** `rebuild_plan` / `consult_persona`). Goat has the same tools plus `rebuild_plan` and `consult_persona`; its `log_result` saves with `source_persona_id=NULL` (see [team-lead.md](team-lead.md)).

## 4. Plan generation — pipeline (decision: priority is SYNCHRONIZATION between personas)

Plan generation **first of all** must produce a consistent, synchronized plan across all active personas (diet matching training, regeneration considered, no load conflicts) — this is more important than maximum quality of a single persona in isolation. Hence **three stages**, not two:

```
Stage 1 — COORDINATOR PASS (cheap model)
  Input: active personas (roles), recent results, previous plan
  Output: shared skeleton — training/rest day layout, priorities,
          indicative goals (e.g. calorie target, intense vs recovery days)
  ~500-1000 tok output, low cost

Stage 2 — PER-PERSONA GENERATION (PLANNER_MODEL, PARALLEL — asyncio.gather)
  Each persona gets: its own system_prompt + its columns/detail_level +
  its results + the skeleton from stage 1 as shared context
  Output: PlanItemContent (draft) for its own days
  Validation + retry PER PERSONA separately (not for the whole)

Stage 3 — HARMONIZATION / "calendar steward" (PLANNER_MODEL)
  Input: ALL draft plan_items from stage 2 together + personas' system prompts
  Task: detect and correct conflicts (e.g. heavy leg training + long run
  same day, diet mismatched to training day, lack of recovery),
  add cross-referencing notes between personas, finalize the calendar.
  Output: TARGETED PATCHES to specific plan_items (not full regeneration
  of everything — cost control), or confirmation that the draft is consistent.
```

**Why 3 stages instead of a single mega-prompt:** with 5 personas the output for a monthly plan reaches 20–45k tokens in a single call — real risk of cutting off JSON mid-way and "diluting" quality for later personas in the queue. Breaking into small, parallel calls + a separate harmonization layer gives controlled cost, cheap retry (per persona, not whole) and **an explicit step responsible for inter-person consistency**, which the "first of all synchronized" priority requires.

A single call (without stages 1 and 3) is allowed only with 1–2 active personas + a weekly plan — there the risk is low and it's cheaper.

### Background job — without a separate worker on Render

**Decision (confirmed):** plan generation runs in the same process as web (FastAPI `BackgroundTasks`), **without** a separate Render Background Worker. Justification and migration threshold in [`devops.md`](devops.md) and [`../adr/decisions.md`](../adr/decisions.md#adr-1).

State model (handling partial success — 4/5 personas ok, 1 failed even after retry):

- `plan_generation_jobs(id, plan_id, status, error_message, attempts, created_at, started_at, finished_at)` — status: `pending|running|success|partial_success|error`, **derived** from per-persona state.
- `plan_generation_job_personas(job_id, persona_id, status, retry_count, last_error)` — per-persona granularity.
- Retrying a single persona **reuses the same `job_id`** (does not create a new one) — otherwise the invariant "max 1 active job per user" (partial unique index in the DB, see [`database-schema.md`](database-schema.md)) breaks on the first partial failure.
- **Reaper** on app startup (`startup` event): `running` jobs older than 5 min → mark as `error` (protects against hanging after Render restart). In MVP reaper **does not** auto-resume — user clicks "regenerate" manually.
- Frontend polls `GET /plans/jobs/{id}` with per-persona breakdown; UI handles `partial_success` as a separate state (not binary success/error) — shows partial plan + banner with the list of personas that failed, with retry action.

### Concurrency — asyncio traps

- `asyncio.gather(*persona_tasks, return_exceptions=True)` for per-persona retry — **not** `asyncio.TaskGroup` (cancels everything on first exception, opposite of the desired behavior).
- Each coroutine takes **its own** DB connection from the pool (`engine.connect()`), never shared between coroutines.
- `asyncio.Semaphore` limiting concurrent LLM/DB calls, chosen for the Supavisor limit and the Render Free plan.
- Blocking operations (e.g. tiktoken on large text) via `asyncio.to_thread` — Render Free is probably 1 uvicorn worker, a block freezes all active SSE streams of other users.

## 5. Chat context — token management

- **User profile (`user_profile`)**: deterministic, concise block (weight/height/age/activity level/goal) attached to the system prompt on EVERY message — this data rarely changes, cheap to always inject. When incomplete, `ContextBuilder` additionally attaches a dynamic "ask about missing data" instruction — see [`ai-pipeline.md`](ai-pipeline.md#0-profil-użytkownika--personalizacja-waga-wzrost-wiek-cel) section 0.
- **Results**: deterministic query of the last N records per category, **without** LLM summarization (unnecessary cost/non-determinism).
- **Chat history**: sliding window of the last M messages. **Decision: no rolling summary in MVP** — only add when production data shows real cutting of important context (data-driven, not designed up-front). Old messages are never deleted from the DB.
- **Plan generation is based on `results` + previous plan + `user_profile` + `persona_constraints`**, not on chat history/summary (too non-deterministic for a 3-stage pipeline). Hard health constraints (e.g. injury mentioned in chat) and biometric data require a separate, explicit mechanism — see [`ai-pipeline.md`](ai-pipeline.md).

## 6. Exceptions and logging

`AppError` hierarchy (`PersonaLimitExceededError`→409, `UsageLimitExceededError`→429, `ModerationRejectedError`→400, `ConflictError`→409, `ExternalServiceError`→502) + global FastAPI exception handler — routers without `try/except`.

`structlog`, JSON in production, `request_id`/`job_id` via `contextvars` (for background jobs you must explicitly bind a new context — request context doesn't propagate automatically). Never full prompt/message contents at INFO level (PII + cost).

## 7. DI and testability

Domain services = Python classes taking dependencies in the constructor (Protocol for `LLMClient`/repo), they don't know FastAPI. `Depends` lives exclusively in `core/dependencies.py`. Unit tests instantiate services directly with fakes — zero FastAPI, zero DB.

Test strategy details in [`ai-pipeline.md`](ai-pipeline.md) (golden cases) and [`devops.md`](devops.md) (CI).

## 8. Authentication

**Decision: Google OAuth only via Supabase Auth — no magic link.** Simplifies the login UI (one "Sign in with Google" button) and eliminates the need to handle transactional emails. Redirect URL configuration in Supabase Auth settings, details in [`local-setup.md`](local-setup.md).

## 9. Limits — USD cost budget per account (ADR-16)

Instead of Free/Pro plans (absent from the rest of the spec — MVP is non-commercial, a few known
users), `UsageLimitService` enforces **an explicit dollar budget per account**
(`profiles.usage_budget_usd`, $10 default, admin-editable — exactly the same pattern as
`profiles.max_active_personas`, ADR-12).

- **Cost counted from OpenRouter response** (`prompt_tokens`/`completion_tokens` returned in the `usage`
  chunk at the end of the SSE stream — requires `usage: {include: true}` in OpenRouter request body) ×
  model pricing. Pricing fetched from OpenRouter's `/api/v1/models` and cached in-memory (refreshed
  periodically, not hardcoded — model prices change).
- `usage_limits.cost_usd_used` — sum of cost in the current period (`(user_id, period_start)`, same
  row as the existing `messages_used`/`tokens_used`/`plan_generations_used` counters).
- **Atomic check+increment** (same pattern as counters): `UPDATE usage_limits SET cost_usd_used =
  cost_usd_used + :delta WHERE cost_usd_used + :delta <= (SELECT usage_budget_usd FROM profiles WHERE
  id = :user_id) RETURNING ...` — race-condition-safe under parallel requests, without a separate
  SELECT-then-UPDATE.
- Plan generation cost (3 LLM calls per stage, see section 4) debits from THIS SAME budget as
  chat — one pool per user, not separate per-function limits.
- Budget exceeded → `UsageLimitExceededError` (429) with a readable message (amount
  used / limit, period renewal date) — `frontend.md` section 10.
- Admin panel (`GET /admin/users`) shows `cost_usd_used`/`usage_budget_usd` directly as an amount,
  **without** "Free"/"Pro" labels (rejected as misleading — suggesting a subscription MVP doesn't have).

## 10. Graft — outside runtime (ADR-20)

Local context graph for coding agents (`graft/`). Does not enter request path, CI, or deploy.
Setup and when to run `graft build`: [`local-setup.md`](local-setup.md) §G. Decision: [`../adr/decisions.md`](../adr/decisions.md#adr-20-graft-jako-lokalna-mapa-kodu-dla-agenta-nie-runtime).
