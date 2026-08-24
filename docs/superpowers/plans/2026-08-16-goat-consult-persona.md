# Goat `consult_persona` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In `general` session without `/slug` the user talks only with Goat; the specialist is consulted by Goat with the `consult_persona` tool (trainer backstage, status "Goat is consulting with {persona}…").

**Architecture:** One `TeamLeadSpeaker` turn with Goat's tool schema + `consult_persona`. Nested trainer turn: `client_visible=False`, `emit_sse=False`, `persist_messages=False`; result returns as tool JSON to Goat. Slash / `persona` session unchanged. End of `plan_consultation` as speaker selection and `format_goat_relay`.

**Tech Stack:** FastAPI, OpenRouter function calling, pytest (`backend/`), Vitest (`frontend/`).

**Spec:** `docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md`

## Global Constraints

- Status copy (verbatim): `Goat is consulting with {label}…` where `{label}` = `persona_display_label(persona)`.
- Tool response error: JSON `{"error": "…"}`, never 500.
- Max **5** `consult_persona` calls per Goat turn (`MAX_CONSULTS_PER_TURN = 5`).
- `consult_persona` only in `get_team_lead_plan_tools()`; trainers don't have it.
- Nested trainer: zero `token` / `persona_turn_start` / `tool_result` on the user queue; zero visible `assistant` message with trainer's `persona_id`.
- Slash (`parse_multi_slash_command`) and `persona` session: Goat does not start.
- Tests: `cd backend && uv run pytest …`; frontend: `cd frontend && npm test -- <file>`.
- Commit step-by-step: **skip**, until the user asks to commit.
- No secrets; docs PL, concrete.

## File map

| File | Role |
|------|------|
| `backend/app/domain/chat/tools.py` | Schema `CONSULT_PERSONA_TOOL_SCHEMA`; Goat registry |
| `backend/app/domain/chat/team_lead.py` | Goat prompt, roster, motor hint, resolve slug, status string; remove relay/speaker classifier |
| `backend/app/domain/chat/orchestrator.py` | `emit_sse`/`persist_messages` flags; consult execution; `run_chat_turn` only Goat or slash |
| `frontend/src/lib/chat-status.ts` | Label + chip `consult_persona` |
| Docs: `team-lead.md`, `ai-pipeline.md` §1a, `adr/decisions.md` ADR-17, `architecture.md` §3a, `AGENTS.md` | Canon after implementation |

---

### Task 1: Schema `consult_persona` + Goat's tool registry

**Files:**
- Modify: `backend/app/domain/chat/tools.py`
- Test: `backend/tests/test_chat_tools_schema.py`

**Interfaces:**
- Produces: `CONSULT_PERSONA_TOOL_SCHEMA: dict[str, Any]`
- Produces: `TEAM_LEAD_CHAT_TOOL_NAMES` contains `"consult_persona"`
- Produces: `get_team_lead_plan_tools()` → `{get_plan, rebuild_plan, update_user_profile, consult_persona}`
- Produces: `get_trainer_chat_tools()` **without** `consult_persona`
- Consumes: existing `get_chat_tools()` (trainers + full set without consult, or consult only in Goat — **don't** add to `get_chat_tools()`)

- [ ] **Step 1: Failing tests**

In `backend/tests/test_chat_tools_schema.py` replace Goat assertions and add:

```python
def test_get_team_lead_plan_tools_includes_consult_persona() -> None:
    names = {t["function"]["name"] for t in get_team_lead_plan_tools()}
    assert names == {
        "get_plan",
        "rebuild_plan",
        "update_user_profile",
        "consult_persona",
    }


def test_trainer_tools_exclude_consult_persona() -> None:
    names = {t["function"]["name"] for t in get_trainer_chat_tools()}
    assert "consult_persona" not in names


def test_consult_persona_schema_requires_slug_and_question() -> None:
    from app.domain.chat.tools import CONSULT_PERSONA_TOOL_SCHEMA

    fn = CONSULT_PERSONA_TOOL_SCHEMA["function"]
    assert fn["name"] == "consult_persona"
    params = fn["parameters"]
    assert set(params["required"]) == {"slug", "question"}
    assert params["additionalProperties"] is False
```

Update `test_get_team_lead_plan_tools_includes_profile` (or delete in favor of the above) and `test_trainer_and_team_lead_tool_sets_disjoint_except_shared`: intersection still `{"get_plan", "update_user_profile"}`; `consult_persona` only in goat.

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/test_chat_tools_schema.py -v
```

Expected: FAIL — no `consult_persona` / `CONSULT_PERSONA_TOOL_SCHEMA`.

- [ ] **Step 3: Schema + registry**

In `tools.py` add (description verbatim from spec):

```python
CONSULT_PERSONA_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "consult_persona",
        "description": (
            "Ask one of the user's active trainers (backstage). Call when you need a "
            "detail from THEIR scope. Motor skills/plyometrics/running/jump → slug of motor_coach "
            "trainer; diet/macros → dietitian; strength/hypertrophy → personal_trainer. "
            "Don't call the wrong role. After the result, answer the user YOURSELF as Goat — don't quote "
            "the trainer in full."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Slug of an active persona from the roster.",
                },
                "question": {
                    "type": "string",
                    "description": "Specific question / brief to the trainer.",
                },
            },
            "required": ["slug", "question"],
            "additionalProperties": False,
        },
    },
}
```

Change:

```python
TEAM_LEAD_CHAT_TOOL_NAMES = frozenset(
    {"get_plan", "rebuild_plan", "update_user_profile", "consult_persona"}
)
```

`get_team_lead_plan_tools`: filter `get_chat_tools() + [CONSULT_PERSONA_TOOL_SCHEMA]` **or** compose the list from Goat's schemas directly (get_plan, rebuild_plan, update_user_profile, consult_persona). Don't put `consult_persona` in `get_chat_tools()`.

- [ ] **Step 4: Run — PASS**

```bash
cd backend && uv run pytest tests/test_chat_tools_schema.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit** — skip (until user asks).

---

### Task 2: Pure helpers — slug, status, prompt, motor hint

**Files:**
- Modify: `backend/app/domain/chat/team_lead.py`
- Test: `backend/tests/test_team_lead.py` (new tests; don't touch old relay/speaker classifier yet)

**Interfaces:**
- Produces: `MAX_CONSULTS_PER_TURN: int = 5`
- Produces: `resolve_persona_by_slug(slug: str, active_personas: list[PersonaLike]) -> PersonaLike | None` (match `p.slug == slug.strip().lstrip("/")`)
- Produces: `goat_consult_status_message(persona: PersonaLike) -> str` → `f"Goat is consulting with {persona_display_label(persona)}…"`
- Produces: `build_goat_turn_prompt(*, active_personas: list[PersonaLike], user_message: str) -> str`
- Produces: `consult_scope_hint(*, message: str, active_personas: list[PersonaLike]) -> str | None`

- [ ] **Step 1: Failing tests** in `test_team_lead.py`

```python
from app.domain.chat.team_lead import (
    MAX_CONSULTS_PER_TURN,
    build_goat_turn_prompt,
    consult_scope_hint,
    goat_consult_status_message,
    resolve_persona_by_slug,
)


def test_max_consults_is_five() -> None:
    assert MAX_CONSULTS_PER_TURN == 5


def test_resolve_persona_by_slug_finds_motor_coach() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    motor = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    assert resolve_persona_by_slug("motoryka", [diet, motor]) is motor
    assert resolve_persona_by_slug("does-not-exist", [diet, motor]) is None


def test_goat_consult_status_message_copy() -> None:
    p = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    assert goat_consult_status_message(p) == "Goat is consulting with Bartek · Motor Skills Trainer…"


def test_consult_scope_hint_motor_not_dietitian() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    motor = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    hint = consult_scope_hint(
        message="How to improve plyometrics and the jump?",
        active_personas=[diet, motor],
    )
    assert hint is not None
    assert "motoryka" in hint
    assert "dietetyk" not in hint.lower() or "not dietitian" in hint.lower()


def test_build_goat_turn_prompt_includes_roster_and_consult_tool() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    motor = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    prompt = build_goat_turn_prompt(
        active_personas=[diet, motor],
        user_message="How to train motor skills?",
    )
    assert "consult_persona" in prompt
    assert "motoryka" in prompt
    assert "dietetyk" in prompt
    assert "plyometrics" in prompt.lower() or "motor_coach" in prompt
```

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/test_team_lead.py::test_resolve_persona_by_slug_finds_motor_coach tests/test_team_lead.py::test_goat_consult_status_message_copy tests/test_team_lead.py::test_consult_scope_hint_motor_not_dietitian tests/test_team_lead.py::test_build_goat_turn_prompt_includes_roster_and_consult_tool tests/test_team_lead.py::test_max_consults_is_five -v
```

Expected: FAIL — import error / missing functions.

- [ ] **Step 3: Implement helpers** in `team_lead.py`

```python
MAX_CONSULTS_PER_TURN = 5

_MOTOR_HINT_NEEDLES = (
    "motor",
    "plyometr",
    "jump",
    "run",
    "speed",
    "dynam",
    "mobil",
    "enduran",
)


def resolve_persona_by_slug(
    slug: str, active_personas: list[PersonaLike]
) -> PersonaLike | None:
    needle = slug.strip().lstrip("/").lower()
    if not needle:
        return None
    return next((p for p in active_personas if p.slug.lower() == needle), None)


def goat_consult_status_message(persona: PersonaLike) -> str:
    return f"Goat is consulting with {persona_display_label(persona)}…"


def consult_scope_hint(*, message: str, active_personas: list[PersonaLike]) -> str | None:
    lower = message.lower()
    motor = next((p for p in active_personas if p.type == "motor_coach"), None)
    if motor is not None and any(n in lower for n in _MOTOR_HINT_NEEDLES):
        return (
            f"Scope hint: the question is about motor skills — if you call consult_persona, "
            f"use the slug `{motor.slug}` (not the dietitian)."
        )
    diet = next((p for p in active_personas if p.type == "dietitian"), None)
    if diet is not None and any(
        n in lower for n in ("eat", "food", "macro", "calor", "meal", "diet")
    ):
        return (
            f"Scope hint: the question is about nutrition — if you call consult_persona, "
            f"use the slug `{diet.slug}`."
        )
    return None
```

Replace `TEAM_LEAD_SYSTEM` / `TEAM_LEAD_PLAN_BEHAVIOR` with one turn prompt (used in `build_goat_turn_prompt` and as `TeamLeadSpeaker.system_prompt` default):

```python
TEAM_LEAD_TURN_BEHAVIOR = """You are Goat — the Team Lead of Trainers. The user talks ONLY with you.
Trainers work backstage through the consult_persona tool. Don't pretend to be a dietitian or motor skills trainer —
when you need a detail from their scope, call consult_persona with the right slug from the roster.

Consult_persona rules:
- Motor skills, plyometrics, jumping, running, speed, dynamics, mobility, endurance → motor_coach slug.
- Diet, macros, meals, calories → dietitian slug.
- Strength, hypertrophy, loads → personal_trainer slug.
- Don't call the wrong role. After the tool response answer YOURSELF — concisely, you can mention who you consulted with,
  but don't paste the trainer's answer in full.
- User asks "let everyone" / for team composition → consult_persona for EACH slug from the roster, then one answer.
- Weekly/monthly plan / rebuild → rebuild_plan (Plans tab). Merit detail in the same
  message → additionally consult_persona.
- update_user_profile only when the user explicitly gives data. Don't call log_result or upsert_plan_items.
Direct trainer conversation: only /slug."""


def build_goat_turn_prompt(*, active_personas: list[PersonaLike], user_message: str) -> str:
    from app.domain.chat.persona_scope import PERSONA_TYPE_SCOPE

    lines = [TEAM_LEAD_TURN_BEHAVIOR, "", "Active trainer roster (slug → consult_persona):"]
    for p in active_personas:
        scope = PERSONA_TYPE_SCOPE.get(p.type, "")
        lines.append(f"- slug=`{p.slug}` | {persona_display_label(p)} | scope: {scope}")
    hint = consult_scope_hint(message=user_message, active_personas=active_personas)
    if hint:
        lines.extend(["", hint])
    if user_requests_all_trainers(user_message):
        slugs = ", ".join(f"`{p.slug}`" for p in active_personas)
        lines.extend(["", f"User asks for the whole team — consult them all: {slugs}."])
    if user_requests_plan_rebuild(user_message):
        lines.extend(["", "User asks for a plan — call rebuild_plan."])
    return "\n".join(lines)
```

`TeamLeadSpeaker.system_prompt` default = `TEAM_LEAD_TURN_BEHAVIOR` (delete the old `TEAM_LEAD_PLAN_BEHAVIOR` or alias it).

`_FakePersona` in tests already has `name` and `slug`.

- [ ] **Step 4: Run — PASS**

```bash
cd backend && uv run pytest tests/test_team_lead.py::test_max_consults_is_five tests/test_team_lead.py::test_resolve_persona_by_slug_finds_motor_coach tests/test_team_lead.py::test_goat_consult_status_message_copy tests/test_team_lead.py::test_consult_scope_hint_motor_not_dietitian tests/test_team_lead.py::test_build_goat_turn_prompt_includes_roster_and_consult_tool -v
```

Expected: PASS.

- [ ] **Step 5: Commit** — skip.

---

### Task 3: Orchestrator — `emit_sse` / `persist_messages` + `consult_persona` execution

**Files:**
- Modify: `backend/app/domain/chat/orchestrator.py` (`handle_message`, `_handle_message_inner`, `_execute_tool_calls`, `_run_single_tool`, `_tool_result_event_payload`)
- Test: `backend/tests/test_consult_persona.py` (new)

**Interfaces:**
- Consumes: `resolve_persona_by_slug`, `goat_consult_status_message`, `MAX_CONSULTS_PER_TURN` (Task 2); `TEAM_LEAD_CHAT_TOOL_NAMES` (Task 1)
- Produces: `handle_message(..., emit_sse: bool = True, persist_messages: bool = True, consult_roster: list | None = None)`
- Produces: tool JSON ok: `{"status": "ok", "slug": str, "persona_label": str, "answer": str}`
- Produces: `_tool_result_event_payload("consult_persona", ...)` → `summary` `Consulted: {persona_label}`, `success` True; on error `success` False

**Nested turn behavior:** `emit_sse=False` → no `_emit` / `_emit_persona_status`. `persist_messages=False` → no `insert_assistant_message` / `insert_tool_message` (trainer tools **do execute** — `log_result` saves the result).

- [ ] **Step 1: Failing tests** — `backend/tests/test_consult_persona.py`

```python
import json
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.chat.orchestrator import ChatOrchestrator, _tool_result_event_payload
from app.domain.chat.team_lead import TeamLeadSpeaker, goat_consult_status_message


@dataclass
class _P:
    id: str
    type: str
    slug: str
    name: str = "X"
    system_prompt: str = "trainer"
    base_template_id: None = None
    persona_constraints: None = None


@pytest.mark.asyncio
async def test_consult_unknown_slug_json_error() -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    orch._consult_roster = [_P(id="a", type="dietitian", slug="dietetyk")]
    orch._consult_count = 0
    raw = await orch._run_single_tool(
        name="consult_persona",
        raw_arguments='{"slug": "motoryka", "question": "plyometrics?"}',
        user_id="u",
        persona=TeamLeadSpeaker(),
        results_service=MagicMock(),
        user_profile_repo=MagicMock(),
        plan_tools=MagicMock(),
    )
    payload = json.loads(raw)
    assert "error" in payload


@pytest.mark.asyncio
async def test_consult_cap_five() -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    orch._consult_roster = [_P(id="a", type="dietitian", slug="dietetyk")]
    orch._consult_count = 5
    raw = await orch._run_single_tool(
        name="consult_persona",
        raw_arguments='{"slug": "dietetyk", "question": "macro?"}',
        user_id="u",
        persona=TeamLeadSpeaker(),
        results_service=MagicMock(),
        user_profile_repo=MagicMock(),
        plan_tools=MagicMock(),
    )
    assert "error" in json.loads(raw)


def test_trainer_blocked_from_consult_persona() -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    trainer = _P(id="a", type="dietitian", slug="dietetyk")
    import asyncio

    raw = asyncio.get_event_loop().run_until_complete(
        orch._run_single_tool(
            name="consult_persona",
            raw_arguments='{"slug": "dietetyk", "question": "x"}',
            user_id="u",
            persona=trainer,
            results_service=MagicMock(),
            user_profile_repo=MagicMock(),
            plan_tools=MagicMock(),
        )
    )
    assert "error" in json.loads(raw)


def test_tool_result_payload_consult_ok() -> None:
    body = json.dumps(
        {
            "status": "ok",
            "slug": "motoryka",
            "persona_label": "Bartek · Motor Skills Trainer",
            "answer": "Plyometrics 2x a week.",
        },
        ensure_ascii=False,
    )
    payload = _tool_result_event_payload("consult_persona", body)
    assert payload["success"] is True
    assert payload["summary"] == "Consulted: Bartek · Motor Skills Trainer"


def test_goat_consult_status_copy_for_sse() -> None:
    p = _P(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    assert goat_consult_status_message(p) == "Goat is consulting with Bartek · Motor Skills Trainer…"
```

For `test_trainer_blocked_from_consult_persona` use `@pytest.mark.asyncio` + `await` (not `run_until_complete`).

Existing guard `team_lead and name not in TEAM_LEAD_CHAT_TOOL_NAMES` **doesn't** block the trainer — add the inverse: if `persona.type != "team_lead"` and `name == "consult_persona"` → JSON error.

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/test_consult_persona.py -v
```

Expected: FAIL — no `_consult_roster` / `consult_persona` branch.

- [ ] **Step 3: Implement**

On `ChatOrchestrator.__init__`:

```python
self._consult_roster: list[Any] | None = None
self._consult_count: int = 0
self._consult_session_id: str | None = None
self._consult_user_queue: asyncio.Queue[dict[str, Any]] | None = None
```

Extend `handle_message` / `_handle_message_inner` with:

```python
emit_sse: bool = True,
persist_messages: bool = True,
consult_roster: list[Any] | None = None,
```

At the start of inner, if `consult_roster is not None`: set `self._consult_roster`, `self._consult_session_id = session_id`, `self._consult_user_queue = queue`. Nested call **without** `consult_roster` doesn't reset the parent's roster — pass `consult_roster` only in Goat's turn. Nested: `consult_roster=None` and **don't** overwrite `self._consult_roster` when argument is `None` and turn is not Goat. Simpler: nested `handle_message` with `persona.type != team_lead` never calls consult (no tool + guard). Roster stays on the instance — OK, because nested has no tool.

Wrap each `_emit` / `_emit_persona_status` in inner: `if emit_sse:`.

In `_execute_tool_calls`: parameter `persist_messages: bool = True`; `insert_assistant_message` / `insert_tool_message` only when True. `_emit(..., "tool_result")` only when `emit_sse` (also pass `emit_sse`).

In `_handle_message_inner` final assistant insert: already under `if client_visible` — change to `if persist_messages and client_visible` (consult: both False).

Branch in `_run_single_tool` **before** `persona_id = persona.id`:

```python
if name == "consult_persona":
    if getattr(persona, "type", None) != "team_lead":
        return json.dumps({"error": "consult_persona available only for Goat."}, ensure_ascii=False)
    return await self._consult_persona(raw_arguments=raw_arguments, user_id=user_id)
```

New method `_consult_persona`:

```python
async def _consult_persona(self, *, raw_arguments: str, user_id: str) -> str:
    roster = self._consult_roster or []
    if self._consult_count >= MAX_CONSULTS_PER_TURN:
        return json.dumps(
            {"error": f"Limit of {MAX_CONSULTS_PER_TURN} consults in this turn."},
            ensure_ascii=False,
        )
    try:
        arguments = json.loads(raw_arguments) if raw_arguments else {}
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"Invalid argument JSON: {exc}"})
    slug = str(arguments.get("slug") or "").strip()
    question = str(arguments.get("question") or "").strip()
    if not slug or not question:
        return json.dumps({"error": "slug and question required."}, ensure_ascii=False)
    target = resolve_persona_by_slug(slug, roster)
    if target is None:
        return json.dumps({"error": f"No active persona with slug {slug!r}."}, ensure_ascii=False)
    self._consult_count += 1
    status = goat_consult_status_message(target)
    user_queue = self._consult_user_queue
    if user_queue is not None:
        await _emit_persona_status(
            user_queue,
            persona=TeamLeadSpeaker(),
            phase="tool",
            message=status,
            tool_name="consult_persona",
        )
    sink: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    ok, answer = await self.handle_message(
        user_id=user_id,
        session_id=self._consult_session_id or "",
        session_type="general",
        persona=target,
        user_message=question,
        queue=sink,
        emit_done=False,
        client_visible=False,
        emit_sse=False,
        persist_messages=False,
        allowed_persona_ids=[p.id for p in roster] if roster else None,
    )
    if not ok or not (answer or "").strip():
        return json.dumps(
            {"error": "Failed to consult the trainer.", "slug": slug},
            ensure_ascii=False,
        )
    label = persona_display_label(target)
    return json.dumps(
        {"status": "ok", "slug": target.slug, "persona_label": label, "answer": answer.strip()},
        ensure_ascii=False,
    )
```

`_tool_result_event_payload` — `consult_persona` branch:

```python
elif name == "consult_persona":
    if parsed.get("error"):
        summary = str(parsed["error"])
        success = False
    else:
        label = str(parsed.get("persona_label") or parsed.get("slug") or "")
        summary = f"Consulted: {label}" if label else "Consulted trainer"
        success = parsed.get("status") == "ok"
```

Set `_consult_session_id` and `_consult_user_queue` at the start of Goat's turn (Task 4); in Task 3 tests unknown slug / cap **don't** call `handle_message`.

Happy-path with a `handle_message` mock (optionally in the same file):

```python
@pytest.mark.asyncio
async def test_consult_happy_path_returns_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    motor = _P(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    orch._consult_roster = [motor]
    orch._consult_count = 0
    orch._consult_session_id = "sess"
    orch._consult_user_queue = None
    async def _fake_handle(**kwargs):
        assert kwargs["persona"].slug == "motoryka"
        assert kwargs["client_visible"] is False
        assert kwargs["persist_messages"] is False
        return True, "Plyometrics 2x."
    monkeypatch.setattr(orch, "handle_message", _fake_handle)
    raw = await orch._consult_persona(
        raw_arguments='{"slug": "motoryka", "question": "how to jump?"}',
        user_id="u",
    )
    data = json.loads(raw)
    assert data["status"] == "ok"
    assert data["answer"] == "Plyometrics 2x."
    assert orch._consult_count == 1
```

- [ ] **Step 4: Run — PASS**

```bash
cd backend && uv run pytest tests/test_consult_persona.py tests/test_chat_tools_schema.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit** — skip.

---

### Task 4: `run_chat_turn` — general without slash = only Goat

**Files:**
- Modify: `backend/app/domain/chat/orchestrator.py` (`_run_chat_turn_body`)
- Test: `backend/tests/test_run_chat_turn_goat.py` (new) — test a **slice** of routing logic, not the full DB stream

Pull out a pure function (easy GWT-1/GWT-5 test):

```python
def general_turn_mode(user_message: str, active_personas: list) -> tuple[str, list]:
    """Returns ('goat', []) or ('slash', [personas...])."""
```

Or test the existing `parse_multi_slash_command` + new helper `should_run_goat_turn(message, personas) -> bool`.

**Interfaces:**
- Produces: `should_run_goat_turn(message: str, active_personas: list[PersonaLike]) -> bool` = `parse_multi_slash_command(...) is None`
- Modify `_run_chat_turn_body`:
  - `general` + Goat: insert user (`invoked_via=None`), `persona_turn_start` Goat, `handle_message` with `TeamLeadSpeaker(system_prompt=build_goat_turn_prompt(...))`, `consult_roster=active_personas`, `client_visible=True`, `emit_sse=True`, `persist_messages=True`; `persona_turn_end` Goat; `turn_complete` + `done`. **Without** trainer loop, **without** `plan_consultation`, **without** `_relay_trainer_response_via_goat`, **without** `build_plan_only_consultation`.
  - `general` + slash: as today persona loop `client_visible=True` (without Goat, without relay).
  - `persona`: unchanged.

Set before Goat's `handle_message`:

```python
orchestrator._consult_roster = list(active_personas)
orchestrator._consult_count = 0
orchestrator._consult_session_id = session_id
orchestrator._consult_user_queue = queue
```

SSE start: `team_phase` / `team_status` = `"Goat is coordinating with the team…"` or directly `persona_turn_start` Goat (not `{slug} is analyzing`).

- [ ] **Step 1: Failing test**

```python
from app.domain.chat.orchestrator import should_run_goat_turn
from app.domain.chat.team_lead import build_goat_turn_prompt

def test_should_run_goat_turn_without_slash() -> None:
    personas = [_FakePersona(id="a", type="dietitian", slug="dietetyk")]
    assert should_run_goat_turn("How to improve plyometrics?", personas) is True
    assert should_run_goat_turn("/dietetyk what to eat", personas) is False
```

Place `_FakePersona` in the test or import from `test_team_lead` — better to duplicate the 5-line dataclass in `test_run_chat_turn_goat.py`.

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/test_run_chat_turn_goat.py -v
```

- [ ] **Step 3: Helper + rewrite `_run_chat_turn_body`**

Skeleton of `general` branch (after loading `active_personas`):

```python
from app.domain.chat.routing import parse_multi_slash_command
from app.domain.chat.team_lead import (
    TeamLeadSpeaker,
    build_goat_turn_prompt,
    is_direct_persona_invocation,
    persona_display_label,
)

slash_match = parse_multi_slash_command(user_message, active_personas)
if slash_match is None:
    content = user_message
    invoked_via = None
    # ... insert user, title ...
    goat = TeamLeadSpeaker(
        system_prompt=build_goat_turn_prompt(
            active_personas=active_personas, user_message=content
        )
    )
    orchestrator._consult_roster = list(active_personas)
    orchestrator._consult_count = 0
    orchestrator._consult_session_id = session_id
    orchestrator._consult_user_queue = queue
    await _emit(queue, "persona_turn_start", {
        "persona_id": None,
        "persona_label": TEAM_LEAD_DISPLAY_LABEL,
    })
    ok, _ = await orchestrator.handle_message(
        user_id=user_id,
        session_id=session_id,
        session_type="general",
        persona=goat,
        user_message=content,
        queue=queue,
        emit_done=False,
        allowed_persona_ids=list(personas_by_id.keys()),
        client_visible=True,
        consult_roster=list(active_personas),
    )
    await _emit(queue, "persona_turn_end", {
        "persona_id": None,
        "persona_label": TEAM_LEAD_DISPLAY_LABEL,
    })
    if ok:
        await _emit(queue, "turn_complete", {})
        await queue.put({"event": "done", "data": "{}"})
    return
# else: slash path — existing loop, client_visible=True, without relay
```

Remove imports: `build_plan_only_consultation`, `format_goat_relay`, `TeamLeadService`, `user_requests_plan_rebuild` from orchestrator (heuristics stay in `build_goat_turn_prompt`). Remove `_relay_trainer_response_via_goat`.

`should_run_goat_turn`:

```python
def should_run_goat_turn(message: str, active_personas: list[Any]) -> bool:
    return parse_multi_slash_command(message, active_personas) is None
```

- [ ] **Step 4: Run**

```bash
cd backend && uv run pytest tests/test_run_chat_turn_goat.py tests/test_consult_persona.py tests/test_orchestrator_team_lead.py tests/test_team_lead.py -v
```

Expected: `test_run_chat_turn_goat` PASS; `test_team_lead` old `plan_consultation` / `format_goat_relay` tests may still PASS (code not yet removed) or FAIL if you remove relay in this task — if you remove `_relay` here, leave `format_goat_relay` for Task 6.

- [ ] **Step 5: Commit** — skip.

---

### Task 5: Frontend — consultation status and chip

**Files:**
- Modify: `frontend/src/lib/chat-status.ts`
- Test: `frontend/src/lib/chat-status.test.ts`

**Interfaces:**
- Produces: `TOOL_ACTION_LABELS.consult_persona = "is consulting"`
- Produces: `toolChipLabel("consult_persona") === "Consultation"`
- Produces: `personaToolStatus("Goat · Team Lead", "consult_persona") === "Goat · Team Lead is consulting…"`
- BE overrides status with the full `Goat is consulting with {label}…` via `persona_status.message` (already handled in `useChatTurnRunner`).

- [ ] **Step 1: Failing tests** in `chat-status.test.ts`

```typescript
it("consult_persona: action and chip", () => {
  expect(personaToolStatus("Goat · Team Lead", "consult_persona")).toBe(
    "Goat · Team Lead is consulting…"
  );
  expect(toolChipLabel("consult_persona")).toBe("Consultation");
});
```

Import `toolChipLabel`.

- [ ] **Step 2: Run — FAIL**

```bash
cd frontend && npm test -- src/lib/chat-status.test.ts
```

- [ ] **Step 3: Add mappings** in `chat-status.ts`:

```typescript
consult_persona: "is consulting",
```

In `TOOL_ACTION_LABELS` and in `toolChipLabel`:

```typescript
consult_persona: "Consultation",
```

- [ ] **Step 4: Run — PASS**

```bash
cd frontend && npm test -- src/lib/chat-status.test.ts src/lib/team-lead.test.ts src/components/chat/MessageList.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit** — skip.

---

### Task 6: Remove dead speaker routing + clean up tests

**Files:**
- Modify: `backend/app/domain/chat/team_lead.py` — remove `format_goat_relay`, `build_plan_only_consultation`, `TeamLeadService.plan_consultation` / `_classify_with_briefs` if nothing imports them; keep `user_requests_plan_rebuild`, `user_requests_all_trainers`, `is_plan_coordination_only` (hint in prompt), `parse` re-export not needed
- Modify: `backend/tests/test_team_lead.py` — remove relay, `build_plan_only_consultation`, `plan_consultation` speaker tests; keep heuristics, `persona_display_label`, new Task 2 helpers
- Modify: `backend/app/domain/chat/routing.py` — docstring: production is Goat's turn + slash, not `plan_consultation`

**Don't touch** `parse_multi_slash_command`.

- [ ] **Step 1: Failing / broken imports** — after removing functions run full pytest, fix imports.

- [ ] **Step 2: Remove dead code** (grep `format_goat_relay`, `plan_consultation`, `build_plan_only_consultation`, `_relay_trainer`).

- [ ] **Step 3: Run**

```bash
cd backend && uv run pytest
```

Expected: PASS, zero failed.

```bash
cd frontend && npm test
```

Expected: PASS.

- [ ] **Step 4: Commit** — skip.

---

### Task 7: Documentation (canon = code)

**Files:**
- Modify: `docs/technical/team-lead.md` — new diagram (Goat + `consult_persona`); tool table + `consult_persona`; remove relay
- Modify: `docs/technical/ai-pipeline.md` §1a — instead of JSON classifier: Goat's turn + tool
- Modify: `docs/adr/decisions.md` ADR-17 — add amendment 2026-08-16 (text from spec, ADR section)
- Modify: `docs/technical/architecture.md` §3a — delta: without slash no speaker loop
- Modify: `AGENTS.md` — chat bullet and Goat: `consult_persona`, not `format_goat_relay`; roundtable = N consults + **one** Goat bubble
- Modify: `.cursor/plans/2026-08-16-goat-consult-persona.md` — status: implemented after tests
- Modify: `docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md` — Status: implemented

- [ ] **Step 1: Update ADR-17** — in `Decision` replace the paragraph about `plan_consultation` / `format_goat_relay`:

```
- **Visibility (2026-08-16):** In `general` without slash a single TeamLeadSpeaker turn.
  Specialist: consult_persona tool (backstage). User sees persona_id=null.
  Exception: /slash and persona session. rebuild_plan in Goat's turn.
```

Consequences: instead of "+1 JSON classifier call" → "0..N consults only when Goat calls the tool".

- [ ] **Step 2: `team-lead.md`** — replace sequenceDiagram with the one from spec; Goat tool table + `consult_persona`.

- [ ] **Step 3: `AGENTS.md`** Learned Preferences chat line: roundtable → one bubble; Workspace Facts: consult tool, not relay.

- [ ] **Step 4: Commit** — skip.

---

## Spec coverage (self-review)

| GWT / requirement | Task |
|-------------------|------|
| GWT-1 only Goat | 4 |
| GWT-2 motor ≠ dietitian (hint + no dietitian speaker) | 2, 4 |
| GWT-3 backstage consult tool | 3 |
| GWT-4 bad slug | 3 |
| GWT-5 slash | 4 |
| GWT-6 roundtable prompt + cap 5 | 2, 3 |
| GWT-7 plan = rebuild_plan in Goat's turn | 2, 4 |
| GWT-8 trainer without consult | 1, 3 |
| SSE copy "Goat is consulting with …" | 2, 3, 5 |
| Remove relay / classifier | 4, 6 |
| Docs / ADR | 7 |

Out of spec scope (don't plan): parallel consults, trainer history persistence, `log_result` for Goat.
