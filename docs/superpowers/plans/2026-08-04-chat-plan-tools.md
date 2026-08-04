# Chat plan tools (Faza 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persony w czacie mogą odczytać plan, dopisać/zaktualizować pozycje dnia w zakładce Plany oraz odpalić pełną przebudowę (3-etapowy pipeline ze wszystkimi aktywnymi personami).

**Architecture:** Trzy nowe function-tools obok `log_result` / `update_user_profile`. Wykonanie w `ChatOrchestrator._execute_tool_calls` przez cienki `ChatPlanToolsService` reużywający `PlansRepo` + ten sam flow co `POST /plans/generate` (BackgroundTasks / `PlanOrchestrator.generate_plan`). Frontend: mapa statusów PL + invalidacja TanStack Query `['plans']` (i istniejący banner joba).

**Tech Stack:** FastAPI, PlansRepo, PlanOrchestrator, OpenAI-compatible tool schemas, Vitest (`chat-status`), pytest.

**Spec:** `docs/superpowers/specs/2026-08-04-chat-multi-persona-and-plans-design.md`  
**Zalecane:** Faza 2 wcześniej (multi-reply przy „uzgodnijcie plan”), ale Faza 3 działa też bez niej.

## Global Constraints

- Błąd walidacji → JSON w tool response, nigdy 500 (wzorzec `log_result`).
- `upsert_plan_items`: domyślnie `persona_id` = wołająca persona; obce id tylko jeśli należy do aktywnych person usera.
- `rebuild_plan` = pełne etapy 1–3 (wszystkie aktywne persony); **nie** sam etap 3 po drobnym upsertcie w MVP.
- Max 1 aktywny job generowania na usera (istniejący partial unique index / ConflictError).
- jsonb przez `CAST(:param AS jsonb)`.
- Statusy FE: dopisać do `TOOL_ACTION_LABELS` w `frontend/src/lib/chat-status.ts`.
- Bez sekretów; docs PL konkretne.

---

### Task 1: Schematy tooli + rejestr w `get_chat_tools`

**Files:**
- Modify: `backend/app/domain/chat/tools.py`
- Test: `backend/tests/test_chat_tools_schema.py` (nowy)

**Interfaces:**
- Produces: `GET_PLAN_TOOL_SCHEMA`, `UPSERT_PLAN_ITEMS_TOOL_SCHEMA`, `REBUILD_PLAN_TOOL_SCHEMA`
- Produces: `get_chat_tools() -> list` z 5 toolami

- [ ] **Step 1: Failing test — get_chat_tools zawiera 5 nazw**

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

- [ ] **Step 2: Run — FAIL (brak 3 nazw)**

- [ ] **Step 3: Add schemas**

Skrót pól:

**get_plan**
```json
{
  "start_date": {"type": "string", "format": "date"},
  "end_date": {"type": "string", "format": "date"}
}
```
Opis PL: „Odczytaj aktualny plan użytkownika (kalendarz Plany). Wołaj przed edycją lub gdy user pyta co jest w planie.”

**upsert_plan_items**
```json
{
  "entries": {
    "type": "array",
    "minItems": 1,
    "items": {
      "type": "object",
      "properties": {
        "item_id": {"type": "string", "description": "Opcjonalne — update istniejącego"},
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
Opis: wołaj gdy user **prosi o zapisanie** treningu/diety w Plany (nie gdy tylko pyta o radę). Nie zgaduj — dopytaj o datę jeśli brak.

**rebuild_plan**
```json
{
  "period_type": {"type": "string", "enum": ["week", "month"]},
  "start_date": {"type": "string", "format": "date"}
}
```
Opis: pełna przebudowa uzgodniona ze **wszystkimi** aktywnymi personami (kosztowna). Tylko gdy user jawnie prosi o wygenerowanie/przebudowę planu.

Zaktualizuj docstring modułu `tools.py` (lista 5 tooli).

- [ ] **Step 4: PASS + commit**

```bash
git commit -m "feat(chat): register get_plan, upsert_plan_items, rebuild_plan tools"
```

---

### Task 2: `ChatPlanToolsService` — get + upsert

**Files:**
- Create: `backend/app/domain/chat/plan_tools.py`
- Modify: `backend/app/repositories/plans_repo.py` (metoda `get_latest_ready_plan_for_user` / `list_items_in_range` jeśli brak)
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

Logika `get_plan`:
1. Znajdź najnowszy plan usera ze statusem `ready` lub `partial_ready` (jeśli brak — `{status:"empty", message:"Brak planu — zaproponuj rebuild_plan lub CTA na /plans"}`).
2. Przefiltruj items po opcjonalnym zakresie dat.
3. Zwróć skrót: `plan_id`, `period_type`, `start_date`, `end_date`, `items: [{id, item_date, item_type, persona_id, title, notes}]` (bez pełnych ogromnych rows jeśli > N — wtedy `rows_preview`).

Logika `upsert_plan_items`:
1. Jeśli brak planu ready → `{error: "Brak planu do edycji. Najpierw rebuild_plan lub wygeneruj na /plans."}`.
2. Per entry: waliduj datę w `[plan.start_date, plan.end_date]`; zbuduj `content` przez `PlanItemContent.model_validate`.
3. Jeśli `item_id` podane: `update_item_content` tylko gdy item należy do planu usera **i** (`item.persona_id == calling` lub admin-bypass — MVP: tylko własna persona).
4. Bez `item_id`: `insert_items` z `persona_id=calling`.
5. Wynik per-entry partial success jak `log_result`.

Dodaj w repo w razie potrzeby:

```python
async def get_latest_plan_for_user(self, user_id: str) -> PlanRow | None:
    # ORDER BY created_at DESC LIMIT 1, status in ('ready','partial_ready')
```

- [ ] **Step 3: PASS + commit**

```bash
git commit -m "feat(chat): ChatPlanToolsService get_plan and upsert_plan_items"
```

---

### Task 3: `rebuild_plan` — enqueue istniejącego pipeline’u

**Files:**
- Modify: `backend/app/domain/chat/plan_tools.py`
- Modify: `backend/app/domain/chat/orchestrator.py` (przekazanie claims + możliwość startu background — patrz niżej)
- Modify: `backend/app/api/routers/chat.py` (jeśli BackgroundTasks musi żyć w request scope)

**Interfaces:**
- Produces: `rebuild_plan(...) -> dict` z `job_id` / `error`
- Consumes: logika jak `plans.generate_plan` (`create_plan` + `create_job` + `PlanOrchestrator.generate_plan`)

**Problem:** `ChatOrchestrator` nie ma `BackgroundTasks`. Opcje (wybrać A):

**A (rekomendowane):** `asyncio.create_task(orchestrator.generate_plan(...))` z claims — ten sam proces co web, jak BackgroundTasks (ADR-1).  
**B:** kolejka w `run_chat_turn` / routerze.

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

- [ ] **Step 2: Implement** — skopiuj formułę `_period_end_date` z `plans.py` do wspólnego helpera `app/domain/plans/period.py` (uniknij duplikacji) albo zaimportuj prywatną funkcję przez przeniesienie.

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
    return {"status": "ok", "job_id": job.id, "plan_id": plan.id, "message": "Generowanie planu uruchomione — wynik w zakładce Plany."}
```

- [ ] **Step 3: PASS + commit**

```bash
git commit -m "feat(chat): rebuild_plan enqueues multi-persona plan pipeline"
```

---

### Task 4: Podpięcie w `ChatOrchestrator._execute_tool_calls` + summary SSE

**Files:**
- Modify: `backend/app/domain/chat/orchestrator.py`
- Modify: helper `_tool_result_summary` (tam gdzie mapowane są summary dla FE)

**Interfaces:**
- Consumes: `ChatPlanToolsService`
- Produces: eventy `tool_result` z `tool_name` / `summary` / `success`

- [ ] **Step 1: Extend dispatch**

```python
if name == "get_plan":
    ...
if name == "upsert_plan_items":
    ...
if name == "rebuild_plan":
    ...
```

Po sukcesie upsert/rebuild: `await _emit(queue, "tool_result", {...})` jak dziś.

Summary przykłady:
- get_plan: `"Plan 2026-08-03–2026-08-09: 12 pozycji"` / `"Brak planu"`
- upsert: `"Zapisano 2 pozycje w Plany"`
- rebuild: `"Uruchomiono przebudowę planu (job …)"`

- [ ] **Step 2: Unit test dispatch z fake service**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(chat): execute plan tools in ChatOrchestrator"
```

---

### Task 5: FE statusy + invalidacja planów

**Files:**
- Modify: `frontend/src/lib/chat-status.ts` (+ test)
- Modify: `frontend/src/hooks/useChatStream.ts` — po `tool_result` dla plan tooli: `invalidateQueries({ queryKey: ['plans'] })` oraz odświeżenie job store jeśli `rebuild_plan` (sprawdź `usePlanGenerationStore` / polling — wystarczy ustawić `jobId` z summary **lub** polegać na tym, że user wejdzie w /plans; lepiej: jeśli event ma `job_id` w payload — rozszerz kontrakt)

**Minimalny kontrakt tool_result (opcjonalne pole):**

```typescript
{ type: 'tool_result', tool_name, summary, success, job_id?: string }
```

Jeśli `job_id` — `usePlanGenerationStore.getState().startPolling(job_id)` (lub istniejący API store).

- [ ] **Step 1: Update TOOL_ACTION_LABELS**

```typescript
get_plan: "przegląda plan",
upsert_plan_items: "zapisuje w Plany",
rebuild_plan: "uzgadnia plan między trenerami",
```

- [ ] **Step 2: Invalidate + optional job_id handling**

- [ ] **Step 3: Tests + commit**

```bash
git commit -m "feat(chat): plan tool status labels and plans cache invalidation"
```

---

### Task 6: Preamble / prompt — kiedy wołać toole planu

**Files:**
- Modify: `backend/app/domain/chat/preamble.py` (krótka sekcja o Plany vs sama rada)
- Modify: `docs/technical/ai-pipeline.md` (sekcja narzędzi czatu)

Tekst dla modelu (PL):  
- Rekomendacja w czacie ≠ zapis w Plany.  
- Gdy user prosi „dodaj do planu / zapisz w Plany” → `upsert_plan_items` lub `rebuild_plan`.  
- Gdy pyta „co mam w planie” → `get_plan`.  
- Nie twierdź, że zapisałeś, dopóki tool_result status ok.

- [ ] **Step 1: Edit preamble + docs**
- [ ] **Step 2: Commit**

```bash
git commit -m "docs: chat plan tools contract and preamble rules"
```

---

### Task 7: Smoke checklist

- [ ] Czat: „co mam w planie na czwartek?” → status „przegląda plan” → odpowiedź z danymi / empty.
- [ ] „Dodaj mobilność w czwartek do planu” → upsert → pozycja widoczna w `/plans` bez odświeżania hard reload (po invalidate).
- [ ] „Przebuduj plan na ten tydzień” → job + banner + wszystkie persony w breakdown.
- [ ] Drugi równoległy rebuild → czytelny error w tool_result, model tłumaczy userowi.
- [ ] Regresja: `log_result` / `update_user_profile` bez zmian.

---

## Self-review (plan)

1. Spec: get / upsert / rebuild / statusy / brak auto-etapu-3 po upsert — pokryte.
2. Brak TBD w krokach krytycznych; helper `_period_end_date` wyciągnięty explicite.
3. Spójność nazw tooli z `chat-status.ts` i `get_chat_tools`.
