# Multi-persona sequential chat turns (Faza 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gdy routing uzna ≥2 role albo user poda kilka slashy, jedna wiadomość usera dostaje N osobnych odpowiedzi asystenta sekwencyjnie w jednym streamie SSE.

**Architecture:** `ChatRoutingService` zwraca uporządkowaną listę `persona_ids` + wspólną treść. `run_chat_turn` wstawia user message raz, potem w pętli emituje `persona_turn_start` i woła istniejący `ChatOrchestrator.handle_message` per personę. Frontend po każdej turze dopina ukończoną odpowiedź do cache historii i resetuje bufor streamu przed następną personą. Statusy z Fazy 1 działają bez zmian (jedna linia naraz).

**Tech Stack:** FastAPI, asyncio.Queue SSE, Pydantic, Vitest, istniejący `useChatStream` / `MessageList`.

**Spec:** `docs/superpowers/specs/2026-08-04-chat-multi-persona-and-plans-design.md`

## Global Constraints

- Sekwencyjnie, nie równolegle — jedna persona kończy zanim startuje następna.
- Max person w jednej turze auto-routingu: `min(liczba_aktywnych, 3)` (stała `CHAT_MAX_PERSONAS_PER_TURN = 3`).
- Multi-slash: kolejność slashy = kolejność odpowiedzi; treść wspólna po ostatnim slugu.
- Jedno `done` na końcu całej tury użytkownika; wiele `persona_turn_start`.
- ADR-13: zaktualizować decyzję „1 persona” → „1..N sekwencyjnie”; bez migracji DB.
- Komunikacja / UI PL; bez sekretów w docs.
- ContextBuilder nadal filtruje historię per `persona_id` (bez zmian w MVP Fazy 2).

---

### Task 1: Multi-slash parser + RoutingResult z listą id

**Files:**
- Modify: `backend/app/domain/chat/routing.py`
- Test: `backend/tests/test_chat_routing.py`

**Interfaces:**
- Produces: `RoutingResult(persona_ids: list[str], invoked_via: Literal[...], content: str)`
- Produces: `parse_multi_slash_command(message, active) -> tuple[list[PersonaLike], str] | None`
- Consumes: istniejące `PersonaLike`, `ChatRoutingService.route`

- [ ] **Step 1: Write failing tests for multi-slash and RoutingResult shape**

```python
def test_parse_multi_slash_two_personas():
    result = parse_multi_slash_command(
        "/trener /dietetyk jak połączyć trening z dietą?",
        [_TRAINER, _DIETITIAN],
    )
    assert result is not None
    personas, rest = result
    assert [p.id for p in personas] == [_TRAINER.id, _DIETITIAN.id]
    assert rest == "jak połączyć trening z dietą?"


def test_parse_multi_slash_single_falls_back_to_legacy_shape():
    # jeden slash nadal działa; route zwraca listę 1-elementową
    ...


async def test_route_multi_slash_sets_invoked_via_multi_slash():
    ...
    assert result.persona_ids == [_TRAINER.id, _DIETITIAN.id]
    assert result.invoked_via == "multi_slash"
```

- [ ] **Step 2: Run tests — expect FAIL (brak symboli)**

Run: `cd backend && uv run pytest tests/test_chat_routing.py -k multi_slash -v`  
Expected: FAIL import / AttributeError

- [ ] **Step 3: Implement parser + change RoutingResult**

W `routing.py`:

```python
_MULTI_SLASH_RE = re.compile(
    r"^(?:/([a-z0-9_]+)\s+)+(.+)$",  # nie używaj ślepo — zaimplementuj pętlę
)

def parse_multi_slash_command(
    message: str, active_personas: list[PersonaLike]
) -> tuple[list[PersonaLike], str] | None:
    """Wszystkie `/slug` na początku (kolejność zachowana, dedupe po id).
    Wymaga ≥1 znanego slugu; nieznany slug w prefiksie → None (klasyfikator)."""
    text = message.strip()
    personas: list[PersonaLike] = []
    seen: set[str] = set()
    pos = 0
    while True:
        m = re.match(r"/([a-z0-9_]+)(?:\s+|$)", text[pos:])
        if m is None:
            break
        slug = m.group(1)
        match_persona = next((p for p in active_personas if p.slug == slug), None)
        if match_persona is None:
            return None
        if match_persona.id not in seen:
            personas.append(match_persona)
            seen.add(match_persona.id)
        pos += m.end()
    if not personas:
        return None
    rest = text[pos:].strip()
    if not rest:
        return None
    return personas, rest


@dataclass(frozen=True, slots=True)
class RoutingResult:
    persona_ids: list[str]
    invoked_via: Literal["slash_command", "multi_slash", "auto_routed"]
    content: str
```

Zaktualizuj `route()`:
1. `parse_multi_slash_command` — jeśli `len(personas) > 1` → `multi_slash`; jeśli 1 → `slash_command` (kompatybilność).
2. Usuń stary `parse_slash_command` **albo** zostaw jako wrapper wołający multi (1 wynik).
3. Wszystkie returny: `persona_ids=[...]` zamiast `persona_id=`.

- [ ] **Step 4: Fix all call sites / tests using `.persona_id`**

Grep: `RoutingResult` / `.persona_id` w `backend/`.  
`orchestrator.run_chat_turn` jeszcze nie pętli — tymczasowo `persona_ids[0]` OK do Task 3, ale typ już lista.

- [ ] **Step 5: Run full routing tests — PASS**

Run: `uv run pytest tests/test_chat_routing.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/chat/routing.py backend/tests/test_chat_routing.py
git commit -m "feat(chat): route to ordered persona_ids including multi-slash"
```

---

### Task 2: Klasyfikator JSON → `persona_ids[]`

**Files:**
- Modify: `backend/app/domain/chat/routing.py` (`_classify` + schema)
- Test: `backend/tests/test_chat_routing.py`

**Interfaces:**
- Consumes: `RoutingResult`, `complete_json`
- Produces: `_classify(...) -> list[str]` (1..CHAT_MAX_PERSONAS_PER_TURN)

- [ ] **Step 1: Failing test — classifier returns two ids**

```python
async def test_route_classifier_can_return_multiple_persona_ids():
    llm = _FakeLLMClient(response={
        "persona_ids": [_TRAINER.id, _DIETITIAN.id],
    })
    service = ChatRoutingService(llm, _FakeChatRepo(), chat_model="m")
    result = await service.route(
        session_id="s1",
        message="Ułóż trening nóg i powiedz co jeść potem",
        active_personas=[_TRAINER, _DIETITIAN],
    )
    assert result.persona_ids == [_TRAINER.id, _DIETITIAN.id]
    assert result.invoked_via == "auto_routed"
```

- [ ] **Step 2: Run — FAIL (schema expects persona_id)**

- [ ] **Step 3: Update prompt + json_schema**

```python
CHAT_MAX_PERSONAS_PER_TURN = 3

# schema properties:
"persona_ids": {
  "type": "array",
  "items": {"type": "string", "enum": ids},
  "minItems": 1,
  "maxItems": min(len(ids), CHAT_MAX_PERSONAS_PER_TURN),
  "uniqueItems": True,
}
# required: ["persona_ids"]
```

System prompt PL: wybierz 1..K person (K=max), **tylko gdy pytanie realnie wymaga wielu ról**; inaczej dokładnie jedną. Kolejność = kolejność odpowiedzi.

Walidacja odpowiedzi:
- filtruj id spoza allowlisty,
- dedupe zachowując kolejność,
- pusta lista → fallback jak dziś (last responding / first active) jako `[id]`,
- obetnij do `CHAT_MAX_PERSONAS_PER_TURN`.

Zachowaj kompatybilność: jeśli LLM zwróci legacy `{persona_id: "..."}` → owrapuj w listę 1-el.

- [ ] **Step 4: Tests PASS + commit**

```bash
git commit -m "feat(chat): classifier returns ordered persona_ids up to 3"
```

---

### Task 3: `run_chat_turn` — pętla sekwencyjna po personach

**Files:**
- Modify: `backend/app/domain/chat/orchestrator.py` (`_run_chat_turn_inner`)
- Test: `backend/tests/test_run_chat_turn_multi.py` (nowy; mock orchestrator/LLM)

**Interfaces:**
- Consumes: `RoutingResult.persona_ids`, `ChatOrchestrator.handle_message`
- Produces: N × `persona_turn_start` + stream per persona; jedno `done` z `handle_message` ostatniej **albo** emit `done` raz po pętli jeśli `handle_message` dziś emituje `done` za każdym razem

**Uwaga krytyczna:** sprawdź czy `handle_message` emituje `done` na końcu. Jeśli tak — przy multi:
- albo parametr `emit_done: bool = True` na ostatniej iteracji,
- albo zdejmij `done` z `handle_message` i emituj wyłącznie w `run_chat_turn` po pętli.

Router SSE kończy się na pierwszym `done` — **musi być dokładnie jedno `done` na końcu**.

- [ ] **Step 1: Inspect current done emission; write failing integration-style test**

```python
async def test_run_chat_turn_emits_two_persona_turn_starts_before_single_done():
    # fake routing returns 2 ids; fake handle_message appends events
    events = []
    # ...
    assert [e for e in events if e["event"] == "persona_turn_start"] == 2
    assert sum(1 for e in events if e["event"] == "done") == 1
    assert events[-1]["event"] == "done"
```

- [ ] **Step 2: Implement loop**

```python
# po insert user message (raz, content=routing.content, invoked_via=routing.invoked_via)
for index, persona_id in enumerate(routing.persona_ids):
    persona = next(p for p in active_personas if p.id == persona_id)
    await _emit(queue, "persona_turn_start", {
        "persona_id": persona.id,
        "persona_label": persona.name,
    })
    await orchestrator.handle_message(
        ...,
        persona=persona,
        user_message=content,
        queue=queue,
        emit_done=(index == len(routing.persona_ids) - 1),
    )
```

Dla sesji `persona` (1:1): `persona_ids = [session.persona_id]` — bez zmian zachowania.

- [ ] **Step 3: Tests PASS + commit**

```bash
git commit -m "feat(chat): sequential multi-persona turns in one SSE stream"
```

---

### Task 4: FE — finalizacja tury persony w `useChatStream`

**Files:**
- Modify: `frontend/src/hooks/useChatStream.ts`
- Modify: `frontend/src/types/chat-stream.ts` (opcjonalnie event `persona_turn_end` — **preferuj detekcję kolejnego `persona_turn_start` / `done`**)
- Test: `frontend/src/hooks/useChatStream.test.ts` (nowy, z mockowanym async generator SSE)

**Interfaces:**
- Consumes: kolejne `persona_turn_start` w jednym `for await`
- Produces: po starcie nowej tury (gdy jest już content/toolResults poprzedniej) — `queryClient.setQueryData` z syntetyczną wiadomością `assistant` + reset `content`/`toolResults`/`pendingContentRef`, nowy `statusLabel`

- [ ] **Step 1: Failing unit test — dwa persona_turn_start → dwie wiadomości w cache**

Mock `streamChatMessage` yields:
1. persona_turn_start A
2. token "cześć"
3. persona_turn_start B
4. token "witaj"
5. done

Assert: po streamie `messagesKey` ma 2 assistant (lub w trakcie: po evencie 3 już 1 assistant w cache + streaming B).

- [ ] **Step 2: Implement `finalizeStreamingTurn(sessionId)`**

```typescript
function finalizeStreamingTurn(
  queryClient: QueryClient,
  sessionId: string,
  streaming: StreamingAssistantMessage,
): void {
  if (!streaming.content && streaming.toolResults.length === 0) return;
  const id = `streamed-${streaming.personaId ?? "x"}-${Date.now()}`;
  queryClient.setQueryData<ChatMessage[]>(messagesKey(sessionId), (old) => [
    ...(old ?? []),
    {
      id,
      session_id: sessionId,
      role: "assistant",
      content: streaming.content,
      tool_calls: null,
      persona_id: streaming.personaId,
      invoked_via: null,
      created_at: new Date().toISOString(),
    },
  ]);
}
```

Na `persona_turn_start`: najpierw `finalize` poprzedniego (flush RAF sync), potem ustaw nową personę + status.

Chipów tool_result: albo dopnij jako osobne wiersze w MessageList z historii (dziś znikają po refresh) — w MVP zostaw tylko w streamie bieżącej tury; po finalize historii bez chipów (jak dziś).

- [ ] **Step 3: Tests PASS + commit**

```bash
git commit -m "feat(chat): finalize assistant turn before next persona in stream"
```

---

### Task 5: Docs + ADR-13 update

**Files:**
- Modify: `docs/adr/decisions.md` (ADR-13 — sekcja decyzja + konsekwencje)
- Modify: `docs/technical/architecture.md` §3a
- Modify: `docs/technical/frontend.md` §3–4
- Modify: `docs/technical/ai-pipeline.md` (klasyfikator multi)

- [ ] **Step 1: Update ADR-13** — routing może zwrócić 1..N; sekwencja; multi-slash; max 3.

- [ ] **Step 2: Update architecture/frontend/ai-pipeline** — kontrakt SSE (wiele `persona_turn_start`, jedno `done`), FE finalize.

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: ADR-13 multi-persona sequential turns"
```

---

### Task 6: Smoke checklist (manual / staging)

- [ ] Sesja general, 1 rola → 1 odpowiedź (regresja).
- [ ] Pytanie trening+dieta → 2 statusy + 2 bubble.
- [ ] `/trener /dietetyk treść` → kolejność zgodna ze slashami.
- [ ] Sesja persona 1:1 bez zmian.
- [ ] Urwanie sieci mid-stream → retry bez duplikatu user message.

---

## Self-review (plan)

1. Spec coverage: multi-slash, classifier N, sequential loop, single done, FE finalize, docs — Tasks 1–5.
2. Placeholders: brak TBD.
3. Types: `persona_ids: list[str]` spójne w BE; FE bez nowego typu event jeśli finalize na kolejnym `persona_turn_start`.
