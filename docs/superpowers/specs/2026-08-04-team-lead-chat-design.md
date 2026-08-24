# Design: Team lead, conversation titles, chat background

**Date:** 2026-08-04  
**Status:** implemented (phase 1 + phase 2) + **ADR-17 deviation** (Goat visible on plan)

> **Canon:** [docs/technical/team-lead.md](../../technical/team-lead.md) · **Audit:** [docs/technical/audits/2026-08-04-goat-team-lead-audit.md](../../technical/audits/2026-08-04-goat-team-lead-audit.md)

## Expert team analysis (synthesis)

### UX/UI
- "New conversation" title on every session — no auto-title from first message; no edit (right-click) and delete.
- Trainer statuses are present, but no "lead is coordinating with team" phase before responses.
- Navigation to Results/Plan interrupts SSE (`abort` + `cancel` on BE side) — user loses the turn.

### Architecture
- Routing (`ChatRoutingService`) picks personas, but **doesn't coordinate** — each persona has isolated history (`persona_id` filter) and doesn't see other recommendations in the same turn → model says "I don't know what the dietitian is doing".
- No superordinate "team lead" role (system, invisible to user).
- No chat task queue — everything ties to SSE connection.

### AI / Python
- `ContextBuilder` has user profile, but **no** plans summary or recent results.
- `upsert_plan_items` requires an existing `ready|partial_ready` plan and blocks editing others' entries — the lead can't save the agreed plan for trainers.

### Frontend
- `useChatStream` lives in `ChatWindow` — unmount = abort. Pattern to copy: `usePlanGenerationStore` + polling in `AppShell`.

## Product decisions

| Topic | Decision |
|-------|---------|
| Team lead | System persona (prompt in code); **visible as "Goat · Team Lead"** during plan operations; invisible for regular questions |
| General conversation flow | (1) lead plans consultation → (2) status "Agreeing with…" → (3) trainers respond sequentially with brief + prior recommendations → (4) `done` |
| Conversation title | Auto from the first ~60 chars of the user's first message; PATCH edit; right-click → "Change title" / "Delete" |
| Background | BE doesn't cancel orchestrator on SSE disconnect; FE: global runner in AppShell (like plan jobs) |
| Persona memory | `[PLAN]` and `[RECENT RESULTS]` blocks in system prompt + tools unchanged |
| Plan save | `upsert_plan_items` accepts `persona_id` in entry (any active user persona); lead can delegate save |

## SSE contract (extension)

```ts
{ type: "team_status", message: "Agreeing with dietitian and trainer…" }
{ type: "turn_complete" }  // optionally before done — signal team done
```

Existing: `persona_turn_start`, `token`, `tool_call_start`, `tool_result`, `done`, `error`.

## API (new)

| Method | Path | Description |
|--------|------|-------------|
| PATCH | `/chat/sessions/{id}` | `{ title: string }` |
| DELETE | `/chat/sessions/{id}` | Deletes session + messages (FK cascade) |
| GET | `/chat/sessions/{id}/turn-status` | `{ in_progress: bool }` |

## Out of scope for this iteration

- Full `chat_turn_jobs` table in Postgres (Render Free = one instance; in-memory registry suffices at start).
- Parallel trainer responses (stays sequence).
- Visible lead messages in chat during **plan operations** (Goat); for regular questions user sees only trainers.

## ADR (proposal)

**ADR-17:** `general` session is coordinated by a system Team Lead before delegating to user personas. Slash/multi-slash routing remains deterministic (skips the lead).

### Known trade-offs (ADR-17, 2026-08-04)

| Scenario | Behavior |
|----------|----------|
| Plan-only without merit questions | Only Goat (`is_plan_coordination_only`) — trainers skipped, even with multi-slash |
| Plan-only | `build_plan_only_consultation` skips the consultation LLM (1 call less) |
| Multi-slash + plan-only | Slash picks personas in routing, but turn ends after Goat |
| Stream retry | Not idempotent for `rebuild_plan` — may repeat plan job |
| `persona` 1:1 session | No Goat and no `rebuild_plan` — harmonize via General conversation or Plans tab |

Legacy `ChatRoutingService` replaced by `TeamLeadService` — to be removed in P2.

---

## Phase 2 — implemented extensions

| Topic | Implementation |
|-------|----------------|
| SSE statuses | `persona_status` (thinking/writing/tool/wrapping_up/done), `team_phase`, `persona_turn_end` |
| Postgres queue | `background_jobs` (`0008_background_jobs.sql`) + `domain/jobs/runner.py` |
| LLM auto-title | `chat_title` job, env `CHAT_LLM_TITLE_ENABLED=true` |
| Harmonization after upsert | `plan_harmonize` job for touched days, `PLAN_AUTO_HARMONIZE_ON_UPSERT=true` |
| Plan enqueue | `enqueue_plan_generation_async` — `/plans/generate` and `rebuild_plan` |
| Turn in background | `chat_sessions.turn_in_progress` + in-memory registry |

### Full SSE contract

```ts
{ type: "team_phase", phase: "planning" | "delegating", message: string }
{ type: "team_status", message: string }
{ type: "persona_turn_start", persona_id, persona_label }
{ type: "persona_status", persona_id, persona_label, phase, message, tool_name? }
{ type: "persona_turn_end", persona_id, persona_label }
{ type: "turn_complete" }
{ type: "token", text }
{ type: "tool_call_start", name }
{ type: "tool_result", tool_name, summary, success }
{ type: "done" } | { type: "error", message }
```

### Migration

Run `supabase/migrations/0008_background_jobs.sql` in SQL Editor (cloud + local Postgres).
