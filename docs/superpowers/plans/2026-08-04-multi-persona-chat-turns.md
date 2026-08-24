# Multi-persona sequential chat turns (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When routing considers ≥2 roles or the user provides multiple slashes, one user message gets N separate assistant responses sequentially in one SSE stream.

**Architecture:** `ChatRoutingService` returns an ordered list of `persona_ids` + shared content. `run_chat_turn` inserts the user message once, then in a loop emits `persona_turn_start` and calls the existing `ChatOrchestrator.handle_message` per persona. The frontend, after each persona's turn, pins the completed response to the history cache and resets the stream buffer before the next persona. Statuses from Phase 1 work without changes (one line at a time).

**Tech Stack:** FastAPI, asyncio.Queue SSE, Pydantic, Vitest, existing `useChatStream` / `MessageList`.

**Spec:** `docs/superpowers/specs/2026-08-04-chat-multi-persona-and-plans-design.md`

## Global Constraints

- Sequentially, not in parallel — one persona ends before the next starts.
- Max personas in one auto-routing turn: `min(number_active, 3)` (constant `CHAT_MAX_PERSONAS_PER_TURN = 3`).
- Multi-slash: order of slashes = order of responses; shared content after the last slash.
- One `done` at the end of the user's entire turn; multiple `persona_turn_start`.
- ADR-13: update "1 persona" → "1..N sequentially" decision; no DB migration.
- Communication / UI in PL; no secrets in docs.
- ContextBuilder still filters history per `persona_id` (no change in MVP Phase 2).

---

### Task 1: Multi-slash parser + RoutingResult with id list

**Files:**
- Modify: `backend/app/domain/chat/routing.py`
- Test: `backend/tests/test_chat_routing.py`

**Interfaces:**
- Produces: `RoutingResult(persona_ids: list[str], invoked_via: Literal[...], content: str)`
- Produces: `parse_multi_slash_command(message, active) -> tuple[list[PersonaLike], str] | None`
- Consumes: existing `PersonaLike`, `ChatRoutingService.route`

- [ ] **Step 1: Write failing tests for multi-slash and RoutingResult shape**

```python
def test_parse_multi_slash_two_personas():
    result = parse_multi_slash_command(
        "/trainer /dietitian how to combine training with diet?",
        [_TRAINER, _DIETITIAN],
    )
    assert result is not None
    personas, rest = result
    assert [p.id for p in personas] == [_TRAINER.id, _DIETITIAN.id]
    assert rest == "how to combine training with diet?"


def test_parse_multi_slash_single_falls_back_to_legacy_shape():
    # one slash still works; route returns a 1-element list
    ...


async def test_route_multi_slash_sets_invoked_via_multi_slash():
    ...
    assert result.persona_ids == [_TRAINER.id, _DIETITIAN.id]
    assert result.invoked_via == "multi_slash"
```

- [ ] **Step 2: Run tests — expect FAIL (no symbols)**

Run: `cd backend && uv run pytest tests/test_chat_routing.py -k multi_slash -v`  
Expected: FAIL import / AttributeError

- [ ] **Step 3: Implement parser + change RoutingResult**

In `routing.py`:

```python
_MULTI_SLASH_RE = re.compile(
    r"^(?:/([a-z0-9_]+)\s+)+(.+)$",  # don't use blindly — implement the loop
)

def parse_multi_slash_command(
    message: str, active_personas: list[PersonaLike]
) -> tuple[list[PersonaLike], str] | None:
    """All `/slug` at the start (order preserved, dedupe by id).
    Requires ≥1 known slug; unknown slug in prefix → None (classifier)."""
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

Update `route()`:
1. `parse_multi_slash_command` — if `len(personas) > 1` → `multi_slash`; if 1 → `slash_command` (compatibility).
2. Remove the old `parse_slash_command` **or** leave it as a wrapper calling multi (1 result).
3. All returns: `persona_ids=[...]` instead of `persona_id=`.

- [ ] **Step 4: Fix all call sites / tests using `.persona_id`**

Grep: `RoutingResult` / `.persona_id` in `backend/`.  
`orchestrator.run_chat_turn` doesn't loop yet — temporarily `persona_ids[0]` OK until Task 3, but the type is already a list.

- [ ] **Step 5: Run full routing tests — PASS**

Run: `uv run pytest tests/test_chat_routing.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/chat/routing.py backend/tests/test_chat_routing.py
git commit -m "feat(chat): route to ordered persona_ids including multi-slash"
```

---

### Task 2: JSON classifier → `persona_ids[]`

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
        message="Build a leg training and tell me what to eat after",
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

System prompt PL: pick 1..K personas (K=max), **only when the question really requires multiple roles**; otherwise exactly one. Order = order of responses.

Response validation:
- filter ids outside the allowlist,
- dedupe preserving order,
- empty list → fallback as today (last responding / first active) as `[id]`,
- trim to `CHAT_MAX_PERSONAS_PER_TURN`.

Maintain compatibility: if LLM returns legacy `{persona_id: "..."}` → wrap in 1-element list.

- [ ] **Step 4: Tests PASS + commit**

```bash
git commit -m "feat(chat): classifier returns ordered persona_ids up to 3"
```

---

### Task 3: `run_chat_turn` — sequential loop over personas

**Files:**
- Modify: `backend/app/domain/chat/orchestrator.py` (`_run_chat_turn_inner`)
- Test: `backend/tests/test_run_chat_turn_multi.py` (new; mock orchestrator/LLM)

**Interfaces:**
- Consumes: `RoutingResult.persona_ids`, `ChatOrchestrator.handle_message`
- Produces: N × `persona_turn_start` + stream per persona; one `done` from the last `handle_message` **or** emit `done` once after the loop if `handle_message` today emits `done` every time

**Critical note:** check if `handle_message` emits `done` at the end. If so, for multi:
- either parameter `emit_done: bool = True` on the last iteration,
- or remove `done` from `handle_message` and emit only in `run_chat_turn` after the loop.

The SSE router ends on the first `done` — **there must be exactly one `done` at the end**.

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
# after inserting user message (once, content=routing.content, invoked_via=routing.invoked_via)
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

For `persona` session (1:1): `persona_ids = [session.persona_id]` — no behavior change.

- [ ] **Step 3: Tests PASS + commit**

```bash
git commit -m "feat(chat): sequential multi-persona turns in one SSE stream"
```

---

### Task 4: FE — finalizing a persona's turn in `useChatStream`

**Files:**
- Modify: `frontend/src/hooks/useChatStream.ts`
- Modify: `frontend/src/types/chat-stream.ts` (optionally `persona_turn_end` event — **prefer detecting the next `persona_turn_start` / `done`**)
- Test: `frontend/src/hooks/useChatStream.test.ts` (new, with mocked async SSE generator)

**Interfaces:**
- Consumes: consecutive `persona_turn_start` in one `for await`
- Produces: after start of a new turn (when there's already content/toolResults from the previous) — `queryClient.setQueryData` with a synthetic `assistant` message + reset `content`/`toolResults`/`pendingContentRef`, new `statusLabel`

- [ ] **Step 1: Failing unit test — two persona_turn_start → two messages in cache**

Mock `streamChatMessage` yields:
1. persona_turn_start A
2. token "hi"
3. persona_turn_start B
4. token "welcome"
5. done

Assert: after the stream `messagesKey` has 2 assistants (or during: after event 3 already 1 assistant in cache + streaming B).

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

On `persona_turn_start`: first `finalize` the previous (flush RAF sync), then set new persona + status.

Tool chips: either pin as separate rows in MessageList from history (today they disappear after refresh) — in MVP leave only in the current turn's stream; after finalizing history without chips (as today).

- [ ] **Step 3: Tests PASS + commit**

```bash
git commit -m "feat(chat): finalize assistant turn before next persona in stream"
```

---

### Task 5: Docs + ADR-13 update

**Files:**
- Modify: `docs/adr/decisions.md` (ADR-13 — decision + consequences section)
- Modify: `docs/technical/architecture.md` §3a
- Modify: `docs/technical/frontend.md` §3–4
- Modify: `docs/technical/ai-pipeline.md` (multi classifier)

- [ ] **Step 1: Update ADR-13** — routing may return 1..N; sequence; multi-slash; max 3.

- [ ] **Step 2: Update architecture/frontend/ai-pipeline** — SSE contract (multiple `persona_turn_start`, one `done`), FE finalize.

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: ADR-13 multi-persona sequential turns"
```

---

### Task 6: Smoke checklist (manual / staging)

- [ ] General session, 1 role → 1 answer (regression).
- [ ] Training + diet question → 2 statuses + 2 bubbles.
- [ ] `/trainer /dietitian content` → order matches slashes.
- [ ] Persona 1:1 session unchanged.
- [ ] Network drop mid-stream → retry without duplicate user message.

---

## Self-review (plan)

1. Spec coverage: multi-slash, classifier N, sequential loop, single done, FE finalize, docs — Tasks 1–5.
2. Placeholders: no TBDs.
3. Types: `persona_ids: list[str]` consistent in BE; FE no new event type if finalize on next `persona_turn_start`.
