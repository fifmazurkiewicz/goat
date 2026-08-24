# Design: Multi-persona chat turns + Plans tools

**Date:** 2026-08-04  
**Status:** agreed in brainstorming; Phase 1 (FE statuses) implemented on `feature/chat-streaming-status`

## Product goal

Personas in chat should work like a team of trainers: when the question touches ≥2 roles (or the user provides multiple slashes), the system returns **separate messages sequentially**. Personas should also **read / edit / rebuild the plan** in the Plans tab, with **agreement between all active personas** (not isolated editing of one trainer).

## Phases

| Phase | Scope | Dependencies |
|-------|-------|--------------|
| **1** (done) | PL status line with `persona_turn_start` / `tool_call_start` | — |
| **2** | Routing → N personas; sequential N responses in one SSE turn | Phase 1 (statuses) |
| **3** | Chat tools: plan read, items upsert, rebuild (pipeline 1–3) | Phase 2 recommended (consultation on rebuild); works without it |

## UX / behavior agreements

1. **Multi-reply always, when routing deems it appropriate** (≥2 roles) **or** the user lists multiple personas with slashes.
2. **Sequentially** (A): persona 1 ends (tokens + tools), then 2, etc. — one active status at a time.
3. **Plan:** read + edit day's entries + rebuild; rebuild = existing 3-stage pipeline (all active personas + harmonization).
4. **Edit hybrid:** small day change → `upsert_plan_items` (+ optionally light stage-3 harmonization for touched days in MVP-lite backlog: upsert alone first); "rebuild / build a week" → `rebuild_plan` = `POST /plans/generate` in background.
5. FE statuses map new tools (`get_plan` → "reviewing plan", `upsert_plan_items` → "saving in Plans", `rebuild_plan` → "agreeing on plan…").

## Consciously out of MVP Phase 2–3

- Parallel / interleaved tokens of multiple personas.
- Full harmonization (stage 3) after every small upsert (cost) — upsert without auto-harmonization first; stage 3 only on `rebuild_plan`.
- Changing ContextBuilder so that persona X sees other personas' responses in the same turn (still per `persona_id` filter; plan sync goes via DB `plan_items`, not via chat history).
- Tool for deleting the entire plan / changing `period_type` from chat.

## ADR

**Supersedes fragment ADR-13:** "exactly one persona per turn" → "one or many personas **sequentially** in one user turn, when routing / multi-slash decides so". `general` session, `chat_messages.persona_id` attribution, `persona_turn_start` event — no data model change.

## Contract (summary)

### Phase 2 — routing

```ts
// RoutingResult (BE)
{ persona_ids: string[]; invoked_via: 'slash_command' | 'auto_routed' | 'multi_slash'; content: string }
```

- JSON classifier: `{ "persona_ids": ["uuid", ...] }` — 1..min(N_active, 3) unique ids from allowlist.
- Multi-slash: all `/slug` at the start of message (order = response order), the rest = shared content.
- SSE: repeated `persona_turn_start` → tokens/tools → … → one `done` at the end of the whole turn.
- FE: after a persona's turn ends (before the next), append the completed response to history cache (optimistic), clear stream `content`, keep tool chips per turn or merge into a list.

### Phase 3 — tools

| Tool | Behavior |
|------|----------|
| `get_plan` | Optional `start_date`/`end_date`; returns a summary of the active plan + items in range |
| `upsert_plan_items` | Batch insert/update entries for the calling persona's `persona_id` (or explicit id if in user's allowlist); `PlanItemContent` validation |
| `rebuild_plan` | Creates a job like `POST /plans/generate`; tool response = `{job_id, status}` + FE invalidates `plans` + job banner |

Validation error → tool response JSON to model, never 500 (`log_result` pattern).
