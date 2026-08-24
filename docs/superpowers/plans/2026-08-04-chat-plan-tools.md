# Chat plan tools (Phase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Personas in chat can read the plan, add/update day items in the Plans tab, and trigger a full rebuild (3-stage pipeline with all active personas).

**Architecture:** Three new function-tools alongside `log_result` / `update_user_profile`. Execution in `ChatOrchestrator._execute_tool_calls` via a thin `ChatPlanToolsService` reusing `PlansRepo` + the same flow as `POST /plans/generate` (BackgroundTasks / `PlanOrchestrator.generate_plan`). Frontend: PL status map + TanStack Query invalidation `['plans']` (and existing job banner).

**Tech Stack:** FastAPI, PlansRepo, PlanOrchestrator, OpenAI-compatible tool schemas, Vitest (`chat-status`), pytest.

**Spec:** `docs/superpowers/specs/2026-08-04-chat-multi-persona-and-plans-design.md`  
**Recommended:** Phase 2 first (multi-reply on "agree on the plan"), but Phase 3 also works without it.

## Global Constraints

- Validation error → JSON in tool response, never 500 (pattern from `log_result`).
- `upsert_plan_items`: default `persona_id` = calling persona; foreign id only if it belongs to user's active personas.
- `rebuild_plan` = full stages 1–3 (all active personas); **not** just stage 3 after a small upsert in MVP.
- Max 1 active generation job per user (existing partial unique index / ConflictError).
- jsonb via `CAST(:param AS jsonb)`.
- FE statuses: add to `TOOL_ACTION_LABELS` in `frontend/src/lib/chat-status.ts`.
- No secrets; concrete PL docs.

---

### Task 1: Tool schemas + registry in `get_chat_tools`

**Files:**
- Modify: `backend/app/domain/chat/tools.py`
- Test: `backend/tests/test_chat_tools_schema.py` (new)

**Interfaces:**
- Produces: `GET_PLAN_TOOL_SCHEMA`, `UPSERT_PLAN_ITEMS_TOOL_SCHEMA`, `REBUILD_PLAN_TOOL_SCHEMA`
- Produces: `get_chat_tools() -> list` with 5 tools

- [ ] **Step 1: Failing test — get_chat_tools contains 5 names**

```python
def test_get_chat_tools_includes_plan_tools():
    names = {t["function"]["name"] for t in get_chat_tools()}
    assert names == {
        "log_result",
        "update_user_profile",
        "get_plan",
        "upsert_plan_items",
        "rebuild_plan",
    }
```

- [ ] **Step 2: Run — FAIL (missing 3 names)**

- [ ] **Step 3: Add schemas**

Field overview:

**get_plan**
```json
{
  "start_date": {"type": "string", "format": "date"},
  "end_date": {"type": "string", "format": "date"}
}
```
PL description: "Read the user's current plan (Plans calendar). Call before editing or when the user asks what is in the plan."

**upsert_plan_items**
```json
{
  "entries": {
    "type": "array",
    "minItems": 1,
    "items": {
      "type": "object",
      "properties": {
        "item_id": {"type": "string", "description": "Optional — update existing"},
        "item_date": {"type": "string", "format": "date"},
        "item_type": {"type": "string"},
        "title": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "string"}},
        "rows": {"type": "array", "items": {"type": "object"}},
        "notes": {"type": "string"}
      },
      "required": ["item_date", "item_type", "title", "columns", "rows"]
    }
  }
}
```
Description: call when the user **asks to save** training/diet to Plans (not when just asking for advice). Don't guess — ask for the date if missing.

**rebuild_plan**
```json
{
  "period_type": {"type": "string", "enum": ["week", "month"]},
  "start_date": {"type": "string", "format": "date"}
}
```
Description: full rebuild agreed with **all** active personas (expensive). Only when the user explicitly asks to generate/rebuild the plan.

Update the `tools.py` module docstring (list of 5 tools).

- [ ] **Step 4: PASS + commit**

```bash
git commit -m "feat(chat): register get_plan, upsert_plan_items, rebuild_plan tools"
```

---

### Task 2: `ChatPlanToolsService` — get + upsert

**Files:**
- Create: `backend/app/domain/chat/plan_tools.py`
- Modify: `backend/app/repositories/plans_repo.py` (method `get_latest_ready_plan_for_user` / `list_items_in_range` if missing)
- Test: `backend/tests/test_chat_plan_tools.py`

**Interfaces:**
- Produces:
  ```python
  class ChatPlanToolsService:
      async def get_plan(self, *, user_id: str, start_date: date | None, end_date: date | None) -> dict
      async def upsert_plan_items(self, *, user_id: str, persona_id: str, entries: list[dict]) -> dict
  ```
- Consumes: `PlansRepo`, `PlanItemContent` (Pydantic)

- [ ] **Step 1: Failing tests**

```python
async def test_get_plan_returns_summary_when_plan_exists():
    ...
    out = await service.get_plan(user_id="u1", start_date=None, end_date=None)
    assert out["status"] == "ok"
    assert "plan_id" in out
    assert isinstance(out["items"], list)


async def test_upsert_inserts_item_for_calling_persona():
    ...
    out = await service.upsert_plan_items(user_id="u1", persona_id="p1", entries=[...])
    assert out["status"] == "ok"
    assert out["upserted"] == 1


async def test_upsert_invalid_content_returns_error_dict_not_raise():
    out = await service.upsert_plan_items(..., entries=[{"item_date": "not-a-date", ...}])
    assert "error" in out
```

- [ ] **Step 2: Implement service**

`get_plan` logic:
1. Find the user's latest plan with status `ready` or `partial_ready` (if missing — `{status:"empty", message:"No plan — suggest rebuild_plan or CTA to /plans"}`).
2. Filter items by optional date range.
3. Return a summary: `plan_id`, `period_type`, `start_date`, `end_date`, `items: [{id, item_date, item_type, persona_id, title, notes}]` (without full huge rows if > N — then `rows_preview`).

`upsert_plan_items` logic:
1. If no ready plan → `{error: "No plan to edit. Run rebuild_plan or generate at /plans first."}`.
2. Per entry: validate date within `[plan.start_date, plan.end_date]`; build `content` via `PlanItemContent.model_validate`.
3. If `item_id` given: `update_item_content` only when the item belongs to the user's plan **and** (`item.persona_id == calling` or admin bypass — MVP: own persona only).
4. Without `item_id`: `insert_items` with `persona_id=calling`.
5. Per-entry partial success result like `log_result`.

Add in the repo if needed:

```python
async def get_latest_plan_for_user(self, user_id: str) -> PlanRow | None:
    # ORDER BY created_at DESC LIMIT 1, status in ('ready','partial_ready')
```

- [ ] **Step 3: PASS + commit**

```bash
git commit -m "feat(chat): ChatPlanToolsService get_plan and upsert_plan_items"
```

---

### Task 3: `rebuild_plan` — enqueue existing pipeline

**Files:**
- Modify: `backend/app/domain/chat/plan_tools.py`
- Modify: `backend/app/domain/chat/orchestrator.py` (passing claims + ability to start background — see below)
- Modify: `backend/app/api/routers/chat.py` (if BackgroundTasks must live in request scope)

**Interfaces:**
- Produces: `rebuild_plan(...) -> dict` with `job_id` / `error`
- Consumes: logic like `plans.generate_plan` (`create_plan` + `create_job` + `PlanOrchestrator.generate_plan`)

**Problem:** `ChatOrchestrator` doesn't have `BackgroundTasks`. Options (choose A):

**A (recommended):** `asyncio.create_task(orchestrator.generate_plan(...))` with claims — same process as the web, like BackgroundTasks (ADR-1).  
**B:** queue in `run_chat_turn` / router.

- [ ] **Step 1: Failing test — rebuild returns job_id; ConflictError → error dict**

```python
async def test_rebuild_plan_returns_job_id():
    out = await service.rebuild_plan(user_id="u1", period_type="week", start_date=date(2026, 8, 3), claims=...)
    assert out["status"] == "ok"
    assert out["job_id"]


async def test_rebuild_plan_active_job_conflict():
    ...
    assert "error" in out
```

- [ ] **Step 2: Implement** — copy the `_period_end_date` formula from `plans.py` into a shared helper `app/domain/plans/period.py` (avoid duplication) or import the private function after moving it.

```python
async def rebuild_plan(...):
    try:
        plan = await plans_repo.create_plan(...)
        job = await plans_repo.create_job(plan_id=plan.id, user_id=user_id)
    except ConflictError as exc:
        return {"error": str(exc)}
    asyncio.create_task(
        PlanOrchestrator(get_openrouter_client()).generate_plan(
            plan_id=plan.id, job_id=job.id, user_id=user_id, claims=claims
        )
    )
    return {"status": "ok", "job_id": job.id, "plan_id": plan.id, "message": "Plan generation started — see the Plans tab."}
```

- [ ] **Step 3: PASS + commit**

```bash
git commit -m "feat(chat): rebuild_plan enqueues multi-persona plan pipeline"
```

---

### Task 4: Hook into `ChatOrchestrator._execute_tool_calls` + SSE summary

**Files:**
- Modify: `backend/app/domain/chat/orchestrator.py`
- Modify: helper `_tool_result_summary` (where summaries for FE are mapped)

**Interfaces:**
- Consumes: `ChatPlanToolsService`
- Produces: `tool_result` events with `tool_name` / `summary` / `success`

- [ ] **Step 1: Extend dispatch**

```python
if name == "get_plan":
    ...
if name == "upsert_plan_items":
    ...
if name == "rebuild_plan":
    ...
```

After successful upsert/rebuild: `await _emit(queue, "tool_result", {...})` as today.

Example summaries:
- get_plan: `"Plan 2026-08-03–2026-08-09: 12 items"` / `"No plan"`
- upsert: `"Saved 2 items to Plans"`
- rebuild: `"Started plan rebuild (job …)"`

- [ ] **Step 2: Unit test dispatch with fake service**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(chat): execute plan tools in ChatOrchestrator"
```

---

### Task 5: FE statuses + plan invalidation

**Files:**
- Modify: `frontend/src/lib/chat-status.ts` (+ test)
- Modify: `frontend/src/hooks/useChatStream.ts` — after `tool_result` for plan tools: `invalidateQueries({ queryKey: ['plans'] })` and refresh job store if `rebuild_plan` (check `usePlanGenerationStore` / polling — enough to set `jobId` from summary **or** rely on user entering /plans; better: if the event has `job_id` in payload — extend the contract)

**Minimal tool_result contract (optional field):**

```typescript
{ type: 'tool_result', tool_name, summary, success, job_id?: string }
```

If `job_id` — `usePlanGenerationStore.getState().startPolling(job_id)` (or existing API store).

- [ ] **Step 1: Update TOOL_ACTION_LABELS**

```typescript
get_plan: "reviewing plan",
upsert_plan_items: "saving to Plans",
rebuild_plan: "aligning plan across coaches",
```

- [ ] **Step 2: Invalidate + optional job_id handling**

- [ ] **Step 3: Tests + commit**

```bash
git commit -m "feat(chat): plan tool status labels and plans cache invalidation"
```

---

### Task 6: Preamble / prompt — when to call plan tools

**Files:**
- Modify: `backend/app/domain/chat/preamble.py` (short section on Plans vs just advice)
- Modify: `docs/technical/ai-pipeline.md` (chat tools section)

Model-facing text (PL):  
- A chat recommendation ≠ saving to Plans.  
- When the user asks "add to plan / save to Plans" → `upsert_plan_items` or `rebuild_plan`.  
- When they ask "what's in my plan" → `get_plan`.  
- Don't claim you saved until tool_result status is ok.

- [ ] **Step 1: Edit preamble + docs**
- [ ] **Step 2: Commit**

```bash
git commit -m "docs: chat plan tools contract and preamble rules"
```

---

### Task 7: Smoke checklist

- [ ] Chat: "what's in my plan for Thursday?" → status "reviewing plan" → response with data / empty.
- [ ] "Add mobility on Thursday to the plan" → upsert → item visible in `/plans` without hard refresh (after invalidate).
- [ ] "Rebuild the plan for this week" → job + banner + all personas in breakdown.
- [ ] Second parallel rebuild → clear error in tool_result, model explains to the user.
- [ ] Regression: `log_result` / `update_user_profile` unchanged.

---

## Self-review (plan)

1. Spec: get / upsert / rebuild / statuses / no auto-stage-3 after upsert — covered.
2. No TBDs in critical steps; `_period_end_date` helper extracted explicitly.
3. Tool names consistent with `chat-status.ts` and `get_chat_tools`.
