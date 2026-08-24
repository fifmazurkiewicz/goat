# AI layer — models, moderation, plan generation

## 0. User profile — personalization (weight, height, age, goal)

**Problem:** without biometric data (weight, height, age, sex, activity level, goal) no persona can really personalize training/diet — purely conversational "tell me about yourself" without structure doesn't give data that the planner prompt can reliably rely on.

**Decision:** shared, one-per-user `user_profile` table (not per-persona — weight is one, regardless of which trainer the user talks to). Distinguish from `personas.persona_constraints`, which is specific to a given persona (e.g. "avoid squats" reported to the gym trainer).

**Filling — conversationally, via tool call, not a static form as the main path.** Per the "persona should ask the user for details" assumption: each persona has access to the `update_user_profile` tool, same class as `log_result` (see section 2) — the model calls it when the user provides data in natural conversation, without requiring the user to fill a form before the first conversation.

```python
def update_user_profile(
    height_cm: float | None = None,
    weight_kg: float | None = None,
    date_of_birth: str | None = None,       # ISO 8601 date
    sex: Literal["male", "female", "other"] | None = None,
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"] | None = None,
    primary_goal: Literal["lose_weight", "build_muscle", "improve_endurance", "general_health", "sport_specific"] | None = None,
    notes: str | None = None,
) -> dict: ...
```

Partial update (only the given fields), validation of ranges as in the `user_profile` table (`height_cm` 100-250, `weight_kg` 20-400, enums for `sex`/`activity_level`/`primary_goal`) — validation error is returned to the model as a tool response, not an exception (same pattern as `log_result`).

**When the model calls `update_user_profile` (rules in the tool description + intake instruction):**

| Situation | Save? |
|-----------|-------|
| User explicitly provides a value (e.g. "I weigh 82 kg", "I'm 178 tall", reduction goal) | yes — only this field |
| User provides a persistent note (injury, allergy, preference) | yes — `notes` field |
| Profile incomplete, model asks — user answers concretely | yes |
| Model guesses / infers from context without explicit user declaration | **no** |
| One-time workout result ("5 km today") | **no** — `log_result` |
| User refuses to provide data | **no** — continue conversation |

Access: **trainers** (any persona) and **Goat** (when the user provides profile data in the same turn, e.g. when asking for a plan). Goat also has `log_result` — since 2026-08-17 saves reported results himself, with `source_persona_id=NULL` (see section 2 and [team-lead.md](team-lead.md)).

**Intake instruction — asking at the start of the conversation.** `ContextBuilder` (architecture.md section 5) checks the completeness of `user_profile` (critical fields: `height_cm`, `weight_kg`, `date_of_birth`, `activity_level`, `primary_goal`) before building the system prompt. If anything is missing — it attaches a dynamic instruction to the prompt (NOT part of the platform preamble, separate, generated segment).

```
[CONTEXT: USER PROFILE INCOMPLETE]
Missing: {list of missing fields in English, e.g. "weight, height, activity level"}.
Before moving to actual coaching, ask naturally for the missing data in
the first 1-2 messages of this conversation (not as a rigid survey). When the user
provides them, save them with the update_user_profile tool. Don't block the conversation if the user
doesn't want to provide some field — continue with what you have.
```

This instruction disappears automatically from the prompt when the profile is complete — no separate "is this the first conversation" logic needed, only based on data state.

**Fallback API + UI** — `GET`/`PATCH /api/v1/profile` and the `/profile` tab (manual form). The main path remains conversational via chat. Both paths write to the same table.

**Feeding plan generation.** `user_profile` is passed explicitly to the planner (stages 1 and 2, architecture.md section 4) alongside `persona_constraints` — biometric data influences e.g. calorie goals (dietitian), age/level-appropriate load selection (gym trainer). Missing complete profile **does not block** plan generation (consistent with ADR-8 — we don't add new hard blockers in MVP), but the planner receives information about gaps and can note in the notes that the plan is preliminary/general until the data is completed.

## 1. Models (verify via OpenRouter's `/api/v1/models` at runtime, don't hardcode prices)

| Role | Env | Default |
|---|---|---|
| Chat (all personas, routing, moderation) | `OPENROUTER_CHAT_MODEL` | `x-ai/grok-4-fast` |
| Planner (3-stage pipeline) | `OPENROUTER_PLANNER_MODEL` (empty = same as chat) | as above |

The chat model **is not** stored per-persona in the DB — one env value for the whole application.

Fallback list of at least 2 providers for `chat_model` (e.g. `[anthropic/claude-haiku-4.5, openai/gpt-5-mini]`) — failure of one provider doesn't take down the chat. `require_parameters: true` in OpenRouter provider routing for the planner (so it doesn't route to an endpoint without `json_schema` support).

Indicative cost: ~$0.003/chat message, ~$0.15–0.20/weekly plan generation for 5 personas (3-stage pipeline).

## 1a. Team Lead coordination — Goat (ADR-17, amended 2026-08-16)

Production: **one `TeamLeadSpeaker` turn** in `general` without slashes + `consult_persona` tool
(roster = active personas **of this user**). Slash bypasses Goat. Canon: [team-lead.md](./team-lead.md).

| Step | Description |
|------|-------------|
| Without slash | Only Goat (`persona_id=null`); expert via `consult_persona` (backstage) |
| Slash / multi-slash | Persona directly — Goat does not start |
| Plan | Goat calls `rebuild_plan` in its turn |
| Goat's tools | `get_plan`, `rebuild_plan`, `update_user_profile`, `consult_persona` (max 5) |
| Trainers | `get_trainer_chat_tools()` — **without** `rebuild_plan` / `consult_persona` |

**ADDED 2026-08-22:** a successful consultation additionally emits the SSE event `consult_detail`
(`{tool_call_id, slug, persona_label, question, answer}`) and the tool response carries `question` —
FE shows an expandable preview of "what the trainer answered Goat" under the Goat message
(spec [2026-08-22-goat-consult-transparency-design.md](../superpowers/specs/2026-08-22-goat-consult-transparency-design.md)).

**Golden cases:** question about motor skills → Goat + optionally `consult_persona` on slug `motor_coach`
from the roster (not a dietitian bubble); own persona (e.g. swimming) also in the roster; plan → `rebuild_plan`.

## 1b. LLM cost and USD budget (ADR-16)

Every OpenRouter response in the SSE stream must include the final `usage` chunk
(`prompt_tokens`/`completion_tokens`) — requires `usage: {include: true}` in the request body (by default
OpenRouter doesn't include `usage` in streamed responses). Turn cost counted as
`prompt_tokens * input_price + completion_tokens * output_price` per model pricing.

**Model pricing** fetched from OpenRouter's `GET /api/v1/models` on app startup and cached
in-memory (refreshed periodically, e.g. hourly) — model prices on OpenRouter change, so
they are NOT hardcoded. Fallback: if the model isn't in the current pricing cache (e.g.
temporary `/models` endpoint outage), use the last known value from the cache; if cache is empty (cold
start) — conservative upper-bound estimate, so the limit isn't bypassed when data is missing.

Cost sum saved in `usage_limits.cost_usd_used` (atomic check+increment, `architecture.md`
§9), enforced against `profiles.usage_budget_usd` ($10 default, admin-editable).
Plan generation (3 stages × up to 5 personas in parallel in stage 2) sums the cost of all calls of
this same job into this same pool.

## 2. `log_result` — tool as a batch

**Decision:** `log_result(entries: list[{category, metric, value, unit, date, notes}])`, not a single entry. A workout with 5 exercises = 1 tool call = 1 round, regardless of whether the model decides to batch calls itself (not guaranteed behavior — models often call tools sequentially even when independent). Validation per-entry, partial success possible (3/5 pass, 2 come back as an error to the model in the same tool response, doesn't fail the whole batch).

Validation via `allowed_metrics` (in-memory cache, loaded on app startup — hot-path during streaming) with `is_custom=true` fallback.

**Access:** trainers (`source_persona_id` = persona UUID) and Goat (`source_persona_id=NULL`, since 2026-08-17 — ADR-6 amendment). Column value determined by `_result_source_persona_id()` in `ChatOrchestrator`.

## 3. Chat context — token budget

```
[platform preamble + persona system_prompt]      ~500-1500 tok. (constant)
[results context: last N entries, table]         ~200-500 tok.
[K last raw messages — sliding window]            to fill the budget
[current user message]
```

`MAX_INPUT_TOKENS` per `chat_model` as a hard target (e.g. 6-10k, regardless of the model supporting 128k+ — a matter of cost/latency, not model limit). No rolling summary in MVP (see [`architecture.md`](architecture.md#5-kontekst-czatu--zarządzanie-tokenami)).

**Since 2026-08-04 (ADR-17):** every persona gets deterministic `[TRAINING PLAN]` and `[USER RECENT RESULTS]` blocks in the system prompt (`ContextBuilder`). The `general` session is coordinated by the system **Team Lead (Goat)** (`team_lead.py`) — picks trainers, prepares the brief, passes on prior recommendations in this turn. On request for a weekly/monthly plan, Goat responds visibly in the UI (**"Goat · Team Lead"**), calls `rebuild_plan`; trainers don't have this tool. Session UI: "General conversation". **Canon:** [team-lead.md](./team-lead.md) · **Audit:** [audits/2026-08-04-goat-team-lead-audit.md](./audits/2026-08-04-goat-team-lead-audit.md).

### SSE — statuses per trainer (phase 2)

In addition to `persona_turn_start` / `token` / `tool_*` the backend emits:

| Event | When |
|-------|------|
| `team_phase` | Lead: `planning` / `delegating` |
| `team_status` | Textual status of the lead |
| `persona_status` | Trainer phases: `thinking`, `writing`, `tool`, `wrapping_up`, `done` |
| `persona_turn_end` | End of one persona's turn |
| `turn_complete` | Whole team finished |

FE shows **a single status line** (replace), disappears at first tokens of the response.

### Conversation title (LLM)

First user message → `chat_title` job in `background_jobs` (`CHAT_LLM_TITLE_ENABLED=true`). LLM returns a short title in English; fallback: message truncation when flag is off.

### Task queue in Postgres (`background_jobs`, migration 0008)

| `job_type` | Trigger | Description |
|------------|---------|-------------|
| `plan_generate` | `POST /plans/generate`, `rebuild_plan` | Full 3-stage pipeline |
| `plan_harmonize` | After successful `upsert_plan_items` | Light harmonization of touched days (`PLAN_AUTO_HARMONIZE_ON_UPSERT`) |
| `chat_title` | First message in a session | Auto-title |

Enqueue: `domain/jobs/runner.py` — `enqueue_plan_generation_async` (HTTP `BackgroundTasks` or `asyncio.create_task`), harmonization/title always `create_task`. On API startup: `resume_pending_jobs_on_startup()` + reaper of hung jobs.

## 4. Plan generation — 3 stages, priority: synchronization

Full pipeline description in [`architecture.md`](architecture.md#4-generowanie-planu--pipeline-decyzja-priorytet-to-synchronizacja-między-personami). Key for the AI layer:

**Stage 3 (harmonization)** is a new, dedicated step playing the role of "virtual calendar steward" — it receives the complete draft plan_items from all personas at once and:
- detects load conflicts (e.g. heavy leg training + long run on the same day),
- checks diet consistency with the training plan (intense day → correspondingly higher calorie/carbohydrate target),
- makes sure rest days are actually included,
- adds cross-referencing notes between personas (e.g. dietitian refers to that day's training),
- output as **targeted patch** to specific `plan_items` (corrects only what requires correction), not full regeneration of everything — cost control.

### `persona_constraints` — hard constraints independent of chat

The plan is based only on `results` + previous plan, not on chat history (too non-deterministic). Problem: an injury / medical recommendation mentioned only in chat never reaches the planner without a dedicated mechanism. **Solution:** the `personas.persona_constraints` field — a short note of hard constraints (e.g. injury, exercise prohibition), passed to the planner **explicitly** in every stage (2 and 3) and to the chat `ContextBuilder`, separated from the rest of the context.

**Access (conscious product decision):** the field is **system/operator-only** — end-user **does not** see it in UI nor in API responses (`PersonaOut` doesn't return it) and **cannot** set it via `POST/PATCH /personas` (field removed from create/update DTO; service additionally rejects save attempt). Filling: seed/admin/future operator panel or direct DB write — not a persona form.

### Template `safety_prompt` — medical rules separate from behavior

Alongside `persona_constraints` (per persona instance) the template has a fixed overlay in `app_private.persona_template_safety`, attached on chat/plan by `base_template_id` (service role connection). `default_prompt` / `system_prompt` contain only behavior. Spec: `docs/superpowers/specs/2026-08-04-persona-safety-prompt-design.md`.

## 5. Golden test cases (CI regression)

**Moderation/jailbreak guard** — ~30–50 cases in categories: benign / borderline / explicit jailbreak / red-flag mid-chat / obfuscation (roleplay wrapper, other language, "in verse form"). Gate metric: recall 100% on jailbreak/red-flag as deploy blocker, false-positive rate on benign with a threshold (e.g. <5%). Kept as fixtures + `pytest`, run in CI on every preamble/classifier change.

**Plan quality** — golden set of 5–10 canonical user+persona+results profiles:
- Deterministic assertions as a hard gate: conformance to `json_schema`, all period days covered, metrics from `allowed_metrics` exist, no duplicates, values within `value_min/value_max`.
- LLM-as-judge (cheap model judging sensibility/progression/inter-person consistency) as a directional signal, **not** a hard CI gate (too unstable as a gate) — review alert.
- Fixtures from real (anonymized) prompts/responses collected periodically from production as regression replay.

## 6. Mocking OpenRouter in tests

`respx` (mocks `httpx` at transport level, works with streaming) + manually recorded fixtures of raw SSE chunks from real responses (anonymized, saved as `.txt`/`.jsonl`). Not VCR.py — weak support for async streaming.

## 7. Resilience to OpenRouter outages

`tenacity` retry+backoff on transport **only before the first byte of response** (a stream cannot be safely repeated after sending some tokens to the client). Fallback model list in OpenRouter provider routing.

## 8. Out of MVP scope (consciously deferred)

- **Weekly recap from a persona** — not entering MVP (decision).
- **Garmin/Strava/Apple Health import/sync** — "maybe someday", the generic `results` model will already carry it when the time comes without schema changes.
