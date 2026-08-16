# Goat `consult_persona` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** W sesji `general` bez `/slug` user rozmawia wyłącznie z Goat; specjalistę Goat dopytuje toollem `consult_persona` (trener za kulisami, status „Goat konsultuje z {persona}…”).

**Architecture:** Jedna tura `TeamLeadSpeaker` ze schematem tooli Goat + `consult_persona`. Zagnieżdżona tura trenera: `client_visible=False`, `emit_sse=False`, `persist_messages=False`; wynik wraca jako tool JSON do Goata. Slash / sesja `persona` bez zmian. Koniec `plan_consultation` jako wyboru mówcy i `format_goat_relay`.

**Tech Stack:** FastAPI, OpenRouter function calling, pytest (`backend/`), Vitest (`frontend/`).

**Spec:** `docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md`

## Global Constraints

- Copy statusu (verbatim): `Goat konsultuje z {etykieta}…` gdzie `{etykieta}` = `persona_display_label(persona)`.
- Tool response błędu: JSON `{"error": "…"}`, nigdy 500.
- Max **5** wywołań `consult_persona` na turę Goata (`MAX_CONSULTS_PER_TURN = 5`).
- `consult_persona` tylko w `get_team_lead_plan_tools()`; trenerzy go nie mają.
- Zagnieżdżony trener: zero `token` / `persona_turn_start` / `tool_result` na kolejkę usera; zero widocznej wiadomości `assistant` z `persona_id` trenera.
- Slash (`parse_multi_slash_command`) i sesja `persona`: Goat nie startuje.
- Testy: `cd backend && uv run pytest …`; frontend: `cd frontend && npm test -- <plik>`.
- Commit kroków: **pomiń**, dopóki user nie poprosi o commit.
- Bez sekretów; docs PL, konkretne.

## File map

| Plik | Rola |
|------|------|
| `backend/app/domain/chat/tools.py` | Schema `CONSULT_PERSONA_TOOL_SCHEMA`; rejestr Goat |
| `backend/app/domain/chat/team_lead.py` | Prompt Goata, roster, hint motoryki, resolve slug, status string; usunąć relay/klasyfikator speakerów |
| `backend/app/domain/chat/orchestrator.py` | Flagi `emit_sse`/`persist_messages`; wykonanie consult; `run_chat_turn` tylko Goat albo slash |
| `frontend/src/lib/chat-status.ts` | Label + chip `consult_persona` |
| Docs: `team-lead.md`, `ai-pipeline.md` §1a, `adr/decisions.md` ADR-17, `architecture.md` §3a, `AGENTS.md` | Kanon po wdrożeniu |

---

### Task 1: Schema `consult_persona` + rejestr tooli Goat

**Files:**
- Modify: `backend/app/domain/chat/tools.py`
- Test: `backend/tests/test_chat_tools_schema.py`

**Interfaces:**
- Produces: `CONSULT_PERSONA_TOOL_SCHEMA: dict[str, Any]`
- Produces: `TEAM_LEAD_CHAT_TOOL_NAMES` zawiera `"consult_persona"`
- Produces: `get_team_lead_plan_tools()` → `{get_plan, rebuild_plan, update_user_profile, consult_persona}`
- Produces: `get_trainer_chat_tools()` **bez** `consult_persona`
- Consumes: istniejące `get_chat_tools()` (trenerzy + pełny zestaw bez consult, albo consult tylko w Goat — **nie** dodawaj do `get_chat_tools()`)

- [ ] **Step 1: Failing tests**

W `backend/tests/test_chat_tools_schema.py` zamień asercje Goat i dopisz:

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

Zaktualizuj `test_get_team_lead_plan_tools_includes_profile` (albo usuń na rzecz powyższego) oraz `test_trainer_and_team_lead_tool_sets_disjoint_except_shared`: przecięcie nadal `{"get_plan", "update_user_profile"}`; `consult_persona` tylko w goat.

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/test_chat_tools_schema.py -v
```

Expected: FAIL — brak `consult_persona` / `CONSULT_PERSONA_TOOL_SCHEMA`.

- [ ] **Step 3: Schema + rejestr**

W `tools.py` dodaj (opis verbatim ze specu):

```python
CONSULT_PERSONA_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "consult_persona",
        "description": (
            "Dopytaj jednego aktywnego trenera usera (za kulisami). Wołaj gdy potrzebujesz "
            "szczegółu z JEGO zakresu. Motoryka/plyometria/bieganie/skok → slug trenera "
            "motor_coach; dieta/makro → dietitian; siła/hipertrofia → personal_trainer. "
            "Nie wołaj złej roli. Po wyniku odpowiedz userowi SAM jako Goat — nie cytuj "
            "trenera w całości."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Slug aktywnej persony z rosteru.",
                },
                "question": {
                    "type": "string",
                    "description": "Konkretne pytanie / brief do trenera.",
                },
            },
            "required": ["slug", "question"],
            "additionalProperties": False,
        },
    },
}
```

Zmień:

```python
TEAM_LEAD_CHAT_TOOL_NAMES = frozenset(
    {"get_plan", "rebuild_plan", "update_user_profile", "consult_persona"}
)
```

`get_team_lead_plan_tools`: filtruj `get_chat_tools() + [CONSULT_PERSONA_TOOL_SCHEMA]` **albo** złóż listę ze schematów Goat wprost (get_plan, rebuild_plan, update_user_profile, consult_persona). Nie wkładaj `consult_persona` do `get_chat_tools()`.

- [ ] **Step 4: Run — PASS**

```bash
cd backend && uv run pytest tests/test_chat_tools_schema.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit** — pomiń (dopóki user nie poprosi).

---

### Task 2: Pure helpers — slug, status, prompt, hint motoryki

**Files:**
- Modify: `backend/app/domain/chat/team_lead.py`
- Test: `backend/tests/test_team_lead.py` (nowe testy; stare relay/klasyfikator speakerów jeszcze nie ruszaj)

**Interfaces:**
- Produces: `MAX_CONSULTS_PER_TURN: int = 5`
- Produces: `resolve_persona_by_slug(slug: str, active_personas: list[PersonaLike]) -> PersonaLike | None` (match `p.slug == slug.strip().lstrip("/")`)
- Produces: `goat_consult_status_message(persona: PersonaLike) -> str` → `f"Goat konsultuje z {persona_display_label(persona)}…"`
- Produces: `build_goat_turn_prompt(*, active_personas: list[PersonaLike], user_message: str) -> str`
- Produces: `consult_scope_hint(*, message: str, active_personas: list[PersonaLike]) -> str | None`

- [ ] **Step 1: Failing tests** w `test_team_lead.py`

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
    assert resolve_persona_by_slug("nie-ma", [diet, motor]) is None


def test_goat_consult_status_message_copy() -> None:
    p = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    assert goat_consult_status_message(p) == "Goat konsultuje z Bartek · Trener motoryczny…"


def test_consult_scope_hint_motor_not_dietitian() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    motor = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    hint = consult_scope_hint(
        message="Jak poprawić plyometrię i skok?",
        active_personas=[diet, motor],
    )
    assert hint is not None
    assert "motoryka" in hint
    assert "dietetyk" not in hint.lower() or "nie dietetyk" in hint.lower()


def test_build_goat_turn_prompt_includes_roster_and_consult_tool() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    motor = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    prompt = build_goat_turn_prompt(
        active_personas=[diet, motor],
        user_message="Jak trenować motorykę?",
    )
    assert "consult_persona" in prompt
    assert "motoryka" in prompt
    assert "dietetyk" in prompt
    assert "plyometria" in prompt.lower() or "motor_coach" in prompt
```

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/test_team_lead.py::test_resolve_persona_by_slug_finds_motor_coach tests/test_team_lead.py::test_goat_consult_status_message_copy tests/test_team_lead.py::test_consult_scope_hint_motor_not_dietitian tests/test_team_lead.py::test_build_goat_turn_prompt_includes_roster_and_consult_tool tests/test_team_lead.py::test_max_consults_is_five -v
```

Expected: FAIL — import error / brak funkcji.

- [ ] **Step 3: Implement helpers** w `team_lead.py`

```python
MAX_CONSULTS_PER_TURN = 5

_MOTOR_HINT_NEEDLES = (
    "motoryk",
    "plyometr",
    "skok",
    "bieg",
    "szybkoś",
    "szybkosc",
    "dynamik",
    "mobilno",
    "wydoln",
)


def resolve_persona_by_slug(
    slug: str, active_personas: list[PersonaLike]
) -> PersonaLike | None:
    needle = slug.strip().lstrip("/").lower()
    if not needle:
        return None
    return next((p for p in active_personas if p.slug.lower() == needle), None)


def goat_consult_status_message(persona: PersonaLike) -> str:
    return f"Goat konsultuje z {persona_display_label(persona)}…"


def consult_scope_hint(*, message: str, active_personas: list[PersonaLike]) -> str | None:
    lower = message.lower()
    motor = next((p for p in active_personas if p.type == "motor_coach"), None)
    if motor is not None and any(n in lower for n in _MOTOR_HINT_NEEDLES):
        return (
            f"Wskazówka zakresu: pytanie dotyczy motoryki — jeśli wołasz consult_persona, "
            f"użyj slug `{motor.slug}` (nie dietetyka)."
        )
    diet = next((p for p in active_personas if p.type == "dietitian"), None)
    if diet is not None and any(
        n in lower for n in ("jeść", "jem", "makro", "kalor", "posił", "diet")
    ):
        return (
            f"Wskazówka zakresu: pytanie dotyczy żywienia — jeśli wołasz consult_persona, "
            f"użyj slug `{diet.slug}`."
        )
    return None
```

Zastąp `TEAM_LEAD_SYSTEM` / `TEAM_LEAD_PLAN_BEHAVIOR` jednym promptem tury (użyj w `build_goat_turn_prompt` i jako `TeamLeadSpeaker.system_prompt` default):

```python
TEAM_LEAD_TURN_BEHAVIOR = """Jesteś Goat — Kierownikiem Zespołu Trenerów. User rozmawia WYŁĄCZNIE z Tobą.
Trenerzy pracują za kulisami przez narzędzie consult_persona. Nie udawaj dietetyka ani trenera motorycznego —
gdy potrzebujesz szczegółu z ich zakresu, wołaj consult_persona z właściwym slugiem z rosteru.

Zasady consult_persona:
- Motoryka, plyometria, skok, bieganie, szybkość, dynamika, mobilność, wydolność → slug motor_coach.
- Dieta, makro, posiłki, kalorie → slug dietitian.
- Siła, hipertrofia, obciążenia → slug personal_trainer.
- Nie wołaj złej roli. Po tool response odpowiedz SAM — zwięźle, możesz wspomnieć z kim uzgodniłeś,
  ale nie wklejaj odpowiedzi trenera w całości.
- User prosi „niech każdy” / o skład zespołu → consult_persona dla KAŻDEGO slug z rosteru, potem jedna odpowiedź.
- Plan tygodnia/miesiąca / przebudowa → rebuild_plan (zakładka Plany). Szczegół merytoryczny w tej samej
  wiadomości → dodatkowo consult_persona.
- update_user_profile tylko gdy user jawnie podaje dane. Nie wołaj log_result ani upsert_plan_items.
Bezpośrednia rozmowa usera z trenerem: tylko /slug."""


def build_goat_turn_prompt(*, active_personas: list[PersonaLike], user_message: str) -> str:
    from app.domain.chat.persona_scope import PERSONA_TYPE_SCOPE

    lines = [TEAM_LEAD_TURN_BEHAVIOR, "", "Roster aktywnych trenerów (slug → consult_persona):"]
    for p in active_personas:
        scope = PERSONA_TYPE_SCOPE.get(p.type, "")
        lines.append(f"- slug=`{p.slug}` | {persona_display_label(p)} | zakres: {scope}")
    hint = consult_scope_hint(message=user_message, active_personas=active_personas)
    if hint:
        lines.extend(["", hint])
    if user_requests_all_trainers(user_message):
        slugs = ", ".join(f"`{p.slug}`" for p in active_personas)
        lines.extend(["", f"User prosi o cały zespół — skonsultuj wszystkich: {slugs}."])
    if user_requests_plan_rebuild(user_message):
        lines.extend(["", "User prosi o plan — wołaj rebuild_plan."])
    return "\n".join(lines)
```

`TeamLeadSpeaker.system_prompt` default = `TEAM_LEAD_TURN_BEHAVIOR` (stary `TEAM_LEAD_PLAN_BEHAVIOR` usuń albo aliasuj).

`_FakePersona` w testach już ma `name` i `slug`.

- [ ] **Step 4: Run — PASS**

```bash
cd backend && uv run pytest tests/test_team_lead.py::test_max_consults_is_five tests/test_team_lead.py::test_resolve_persona_by_slug_finds_motor_coach tests/test_team_lead.py::test_goat_consult_status_message_copy tests/test_team_lead.py::test_consult_scope_hint_motor_not_dietitian tests/test_team_lead.py::test_build_goat_turn_prompt_includes_roster_and_consult_tool -v
```

Expected: PASS.

- [ ] **Step 5: Commit** — pomiń.

---

### Task 3: Orchestrator — `emit_sse` / `persist_messages` + wykonanie `consult_persona`

**Files:**
- Modify: `backend/app/domain/chat/orchestrator.py` (`handle_message`, `_handle_message_inner`, `_execute_tool_calls`, `_run_single_tool`, `_tool_result_event_payload`)
- Test: `backend/tests/test_consult_persona.py` (nowy)

**Interfaces:**
- Consumes: `resolve_persona_by_slug`, `goat_consult_status_message`, `MAX_CONSULTS_PER_TURN` (Task 2); `TEAM_LEAD_CHAT_TOOL_NAMES` (Task 1)
- Produces: `handle_message(..., emit_sse: bool = True, persist_messages: bool = True, consult_roster: list | None = None)`
- Produces: tool JSON ok: `{"status": "ok", "slug": str, "persona_label": str, "answer": str}`
- Produces: `_tool_result_event_payload("consult_persona", ...)` → `summary` `Skonsultowano: {persona_label}`, `success` True; przy error `success` False

**Zachowanie zagnieżdżonej tury:** `emit_sse=False` → żadnych `_emit` / `_emit_persona_status`. `persist_messages=False` → żadnych `insert_assistant_message` / `insert_tool_message` (toole trenera **wykonują się** — `log_result` zapisuje wynik).

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
    system_prompt: str = "trener"
    base_template_id: None = None
    persona_constraints: None = None


@pytest.mark.asyncio
async def test_consult_unknown_slug_json_error() -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    orch._consult_roster = [_P(id="a", type="dietitian", slug="dietetyk")]
    orch._consult_count = 0
    raw = await orch._run_single_tool(
        name="consult_persona",
        raw_arguments='{"slug": "motoryka", "question": "plyometria?"}',
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
        raw_arguments='{"slug": "dietetyk", "question": "makro?"}',
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
            "persona_label": "Bartek · Trener motoryczny",
            "answer": "Plyometria 2x tydzień.",
        },
        ensure_ascii=False,
    )
    payload = _tool_result_event_payload("consult_persona", body)
    assert payload["success"] is True
    assert payload["summary"] == "Skonsultowano: Bartek · Trener motoryczny"


def test_goat_consult_status_copy_for_sse() -> None:
    p = _P(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    assert goat_consult_status_message(p) == "Goat konsultuje z Bartek · Trener motoryczny…"
```

Dla `test_trainer_blocked_from_consult_persona` użyj `@pytest.mark.asyncio` + `await` (nie `run_until_complete`).

Istniejący guard `team_lead and name not in TEAM_LEAD_CHAT_TOOL_NAMES` **nie** blokuje trenera — dodaj odwrotny: jeśli `persona.type != "team_lead"` i `name == "consult_persona"` → error JSON.

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/test_consult_persona.py -v
```

Expected: FAIL — brak `_consult_roster` / gałęzi `consult_persona`.

- [ ] **Step 3: Implement**

Na `ChatOrchestrator.__init__`:

```python
self._consult_roster: list[Any] | None = None
self._consult_count: int = 0
self._consult_session_id: str | None = None
self._consult_user_queue: asyncio.Queue[dict[str, Any]] | None = None
```

Rozszerz `handle_message` / `_handle_message_inner` o:

```python
emit_sse: bool = True,
persist_messages: bool = True,
consult_roster: list[Any] | None = None,
```

Na starcie inner, jeśli `consult_roster is not None`: ustaw `self._consult_roster`, `self._consult_session_id = session_id`, `self._consult_user_queue = queue`. Nested wywołanie **bez** `consult_roster` nie zeruje rosteru rodzica — przekaż `consult_roster` tylko w turze Goata. Nested: `consult_roster=None` i **nie** nadpisuj `self._consult_roster` gdy argument jest `None` i tura nie jest Goat. Prościej: nested `handle_message` z `persona.type != team_lead` nigdy nie woła consult (brak w tools + guard). Roster zostaje na instancji — OK, bo nested nie ma toola.

Owiń każde `_emit` / `_emit_persona_status` w inner: `if emit_sse:`.

W `_execute_tool_calls`: parametr `persist_messages: bool = True`; `insert_assistant_message` / `insert_tool_message` tylko gdy True. `_emit(..., "tool_result")` tylko gdy `emit_sse` (przekaż `emit_sse` też).

W `_handle_message_inner` końcowy insert assistant: już pod `if client_visible` — zmień na `if persist_messages and client_visible` (consult: oba False).

Gałąź w `_run_single_tool` **przed** `persona_id = persona.id`:

```python
if name == "consult_persona":
    if getattr(persona, "type", None) != "team_lead":
        return json.dumps({"error": "consult_persona dostępne tylko dla Goata."}, ensure_ascii=False)
    return await self._consult_persona(raw_arguments=raw_arguments, user_id=user_id)
```

Nowa metoda `_consult_persona`:

```python
async def _consult_persona(self, *, raw_arguments: str, user_id: str) -> str:
    roster = self._consult_roster or []
    if self._consult_count >= MAX_CONSULTS_PER_TURN:
        return json.dumps(
            {"error": f"Limit {MAX_CONSULTS_PER_TURN} konsultacji w tej turze."},
            ensure_ascii=False,
        )
    try:
        arguments = json.loads(raw_arguments) if raw_arguments else {}
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"Nieprawidłowy JSON argumentów: {exc}"})
    slug = str(arguments.get("slug") or "").strip()
    question = str(arguments.get("question") or "").strip()
    if not slug or not question:
        return json.dumps({"error": "Wymagane slug i question."}, ensure_ascii=False)
    target = resolve_persona_by_slug(slug, roster)
    if target is None:
        return json.dumps({"error": f"Brak aktywnej persony o slugu {slug!r}."}, ensure_ascii=False)
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
            {"error": "Nie udało się skonsultować trenera.", "slug": slug},
            ensure_ascii=False,
        )
    label = persona_display_label(target)
    return json.dumps(
        {"status": "ok", "slug": target.slug, "persona_label": label, "answer": answer.strip()},
        ensure_ascii=False,
    )
```

`_tool_result_event_payload` — gałąź `consult_persona`:

```python
elif name == "consult_persona":
    if parsed.get("error"):
        summary = str(parsed["error"])
        success = False
    else:
        label = str(parsed.get("persona_label") or parsed.get("slug") or "")
        summary = f"Skonsultowano: {label}" if label else "Skonsultowano trenera"
        success = parsed.get("status") == "ok"
```

Ustaw `_consult_session_id` i `_consult_user_queue` na początku tury Goata (Task 4); w testach Task 3 unknown slug / cap **nie** wołają `handle_message`.

Happy-path z mockiem `handle_message` (opcjonalnie w tym samym pliku):

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
        return True, "Plyometria 2x."
    monkeypatch.setattr(orch, "handle_message", _fake_handle)
    raw = await orch._consult_persona(
        raw_arguments='{"slug": "motoryka", "question": "jak skakać?"}',
        user_id="u",
    )
    data = json.loads(raw)
    assert data["status"] == "ok"
    assert data["answer"] == "Plyometria 2x."
    assert orch._consult_count == 1
```

- [ ] **Step 4: Run — PASS**

```bash
cd backend && uv run pytest tests/test_consult_persona.py tests/test_chat_tools_schema.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit** — pomiń.

---

### Task 4: `run_chat_turn` — general bez slash = tylko Goat

**Files:**
- Modify: `backend/app/domain/chat/orchestrator.py` (`_run_chat_turn_body`)
- Test: `backend/tests/test_run_chat_turn_goat.py` (nowy) — testuj **wycinek** logiki routingu, nie cały DB stream

Wyciągnij czystą funkcję (łatwy test GWT-1/GWT-5):

```python
def general_turn_mode(user_message: str, active_personas: list) -> tuple[str, list]:
    """Zwraca ('goat', []) albo ('slash', [personas...])."""
```

Albo testuj istniejące `parse_multi_slash_command` + nowy helper `should_run_goat_turn(message, personas) -> bool`.

**Interfaces:**
- Produces: `should_run_goat_turn(message: str, active_personas: list[PersonaLike]) -> bool` = `parse_multi_slash_command(...) is None`
- Modify `_run_chat_turn_body`:
  - `general` + Goat: insert user (`invoked_via=None`), `persona_turn_start` Goat, `handle_message` z `TeamLeadSpeaker(system_prompt=build_goat_turn_prompt(...))`, `consult_roster=active_personas`, `client_visible=True`, `emit_sse=True`, `persist_messages=True`; `persona_turn_end` Goat; `turn_complete` + `done`. **Bez** pętli trenerów, **bez** `plan_consultation`, **bez** `_relay_trainer_response_via_goat`, **bez** `build_plan_only_consultation`.
  - `general` + slash: jak dziś pętla person `client_visible=True` (bez Goat, bez relay).
  - `persona`: bez zmian.

Ustaw przed `handle_message` Goata:

```python
orchestrator._consult_roster = list(active_personas)
orchestrator._consult_count = 0
orchestrator._consult_session_id = session_id
orchestrator._consult_user_queue = queue
```

Start SSE: `team_phase` / `team_status` = `"Goat uzgadnia z zespołem…"` albo od razu `persona_turn_start` Goat (nie `{slug} analizuje`).

- [ ] **Step 1: Failing test**

```python
from app.domain.chat.orchestrator import should_run_goat_turn
from app.domain.chat.team_lead import build_goat_turn_prompt

def test_should_run_goat_turn_without_slash() -> None:
    personas = [_FakePersona(id="a", type="dietitian", slug="dietetyk")]
    assert should_run_goat_turn("Jak poprawić plyometrię?", personas) is True
    assert should_run_goat_turn("/dietetyk co jeść", personas) is False
```

Umieść `_FakePersona` w teście albo import z `test_team_lead` — lepiej zduplikuj 5-linijkowy dataclass w `test_run_chat_turn_goat.py`.

- [ ] **Step 2: Run — FAIL**

```bash
cd backend && uv run pytest tests/test_run_chat_turn_goat.py -v
```

- [ ] **Step 3: Helper + przepisz `_run_chat_turn_body`**

Szkielet gałęzi `general` (po załadowaniu `active_personas`):

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
# else: slash path — istniejąca pętla, client_visible=True, bez relay
```

Usuń importy: `build_plan_only_consultation`, `format_goat_relay`, `TeamLeadService`, `user_requests_plan_rebuild` z orchestratora (heurystyki zostają w `build_goat_turn_prompt`). Usuń funkcję `_relay_trainer_response_via_goat`.

`should_run_goat_turn`:

```python
def should_run_goat_turn(message: str, active_personas: list[Any]) -> bool:
    return parse_multi_slash_command(message, active_personas) is None
```

- [ ] **Step 4: Run**

```bash
cd backend && uv run pytest tests/test_run_chat_turn_goat.py tests/test_consult_persona.py tests/test_orchestrator_team_lead.py tests/test_team_lead.py -v
```

Expected: `test_run_chat_turn_goat` PASS; `test_team_lead` stare testy `plan_consultation` / `format_goat_relay` jeszcze mogą PASS (kod jeszcze nie usunięty) albo FAIL jeśli usuniesz relay w tym tasku — jeśli usuniesz `_relay` tutaj, zostaw `format_goat_relay` do Task 6.

- [ ] **Step 5: Commit** — pomiń.

---

### Task 5: Frontend — status i chip konsultacji

**Files:**
- Modify: `frontend/src/lib/chat-status.ts`
- Test: `frontend/src/lib/chat-status.test.ts`

**Interfaces:**
- Produces: `TOOL_ACTION_LABELS.consult_persona = "konsultuje"`
- Produces: `toolChipLabel("consult_persona") === "Konsultacja"`
- Produces: `personaToolStatus("Goat · Kierownik Zespołu", "consult_persona") === "Goat · Kierownik Zespołu konsultuje…"`
- BE nadpisze status pełnym `Goat konsultuje z {etykieta}…` przez `persona_status.message` (już obsługiwane w `useChatTurnRunner`).

- [ ] **Step 1: Failing tests** w `chat-status.test.ts`

```typescript
it("consult_persona: akcja i chip", () => {
  expect(personaToolStatus("Goat · Kierownik Zespołu", "consult_persona")).toBe(
    "Goat · Kierownik Zespołu konsultuje…"
  );
  expect(toolChipLabel("consult_persona")).toBe("Konsultacja");
});
```

Import `toolChipLabel`.

- [ ] **Step 2: Run — FAIL**

```bash
cd frontend && npm test -- src/lib/chat-status.test.ts
```

- [ ] **Step 3: Dopisz mapowania** w `chat-status.ts`:

```typescript
consult_persona: "konsultuje",
```

w `TOOL_ACTION_LABELS` oraz w `toolChipLabel`:

```typescript
consult_persona: "Konsultacja",
```

- [ ] **Step 4: Run — PASS**

```bash
cd frontend && npm test -- src/lib/chat-status.test.ts src/lib/team-lead.test.ts src/components/chat/MessageList.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit** — pomiń.

---

### Task 6: Usunąć martwy routing speakerów + sprzątnąć testy

**Files:**
- Modify: `backend/app/domain/chat/team_lead.py` — usuń `format_goat_relay`, `build_plan_only_consultation`, `TeamLeadService.plan_consultation` / `_classify_with_briefs` jeśli nic nie importuje; zostaw `user_requests_plan_rebuild`, `user_requests_all_trainers`, `is_plan_coordination_only` (hint w promptcie), `parse` re-export niepotrzebny
- Modify: `backend/tests/test_team_lead.py` — usuń testy relay, `build_plan_only_consultation`, `plan_consultation` speakerów; zostaw heurystyki, `persona_display_label`, nowe helpery Task 2
- Modify: `backend/app/domain/chat/routing.py` — docstring: produkcja to tura Goata + slash, nie `plan_consultation`

**Nie ruszaj** `parse_multi_slash_command`.

- [ ] **Step 1: Failing / broken imports** — po usunięciu funkcji odpal pełny pytest, napraw importy.

- [ ] **Step 2: Usuń martwy kod** (grep `format_goat_relay`, `plan_consultation`, `build_plan_only_consultation`, `_relay_trainer`).

- [ ] **Step 3: Run**

```bash
cd backend && uv run pytest
```

Expected: PASS, zero failed.

```bash
cd frontend && npm test
```

Expected: PASS.

- [ ] **Step 4: Commit** — pomiń.

---

### Task 7: Dokumentacja (kanon = kod)

**Files:**
- Modify: `docs/technical/team-lead.md` — nowy diagram (Goat + `consult_persona`); tabela tooli + `consult_persona`; usuń relay
- Modify: `docs/technical/ai-pipeline.md` §1a — zamiast klasyfikatora JSON: tura Goata + tool
- Modify: `docs/adr/decisions.md` ADR-17 — dopisz nowelizację 2026-08-16 (tekst ze specu, sekcja ADR)
- Modify: `docs/technical/architecture.md` §3a — delta: bez slashy nie ma pętli speakerów
- Modify: `AGENTS.md` — bullet czatu i Goat: `consult_persona`, nie `format_goat_relay`; roundtable = N consultów + **jeden** bubble Goata
- Modify: `.cursor/plans/2026-08-16-goat-consult-persona.md` — status: wdrożone po testach
- Modify: `docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md` — Status: wdrożone

- [ ] **Step 1: Zaktualizuj ADR-17** — w `Decyzja` zastąp akapit o `plan_consultation` / `format_goat_relay`:

```
- **Widoczność (2026-08-16):** W `general` bez slashy jedna tura TeamLeadSpeaker.
  Specjalista: tool consult_persona (backstage). User widzi persona_id=null.
  Wyjątek: /slug i sesja persona. rebuild_plan w turze Goata.
```

Konsekwencje: zamiast „+1 wywołanie JSON klasyfikatora” → „0..N consultów tylko gdy Goat woła tool”.

- [ ] **Step 2: `team-lead.md`** — zamień sequenceDiagram na ten ze specu; tabela tooli Goat + `consult_persona`.

- [ ] **Step 3: `AGENTS.md`** Learned Preferences linia czatu: roundtable → jeden bubble; Workspace Facts: consult tool, nie relay.

- [ ] **Step 4: Commit** — pomiń.

---

## Spec coverage (self-review)

| GWT / wymóg | Task |
|-------------|------|
| GWT-1 tylko Goat | 4 |
| GWT-2 motoryka ≠ dietetyk (hint + brak speaker dietetyka) | 2, 4 |
| GWT-3 tool consult backstage | 3 |
| GWT-4 zły slug | 3 |
| GWT-5 slash | 4 |
| GWT-6 roundtable prompt + cap 5 | 2, 3 |
| GWT-7 plan = rebuild_plan w turze Goata | 2, 4 |
| GWT-8 trener bez consult | 1, 3 |
| SSE copy „Goat konsultuje z …” | 2, 3, 5 |
| Usunięcie relay / klasyfikatora | 4, 6 |
| Docs / ADR | 7 |

Poza zakresem specu (nie planować): równoległe consulty, persystencja historii trenera, `log_result` u Goata.
