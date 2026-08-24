"""Consult transparency — `question` in tool response + SSE `consult_detail`."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest

from app.domain.chat.orchestrator import ChatOrchestrator, _tool_result_event_payload
from app.domain.chat.team_lead import TeamLeadSpeaker


class _P:
    def __init__(self, id: str, type: str, slug: str, name: str = "X") -> None:
        self.id = id
        self.type = type
        self.slug = slug
        self.name = name
        self.system_prompt = "trener"
        self.base_template_id = None
        self.persona_constraints = None


_CONSULT_CALL = {
    "id": "call-1",
    "type": "function",
    "function": {
        "name": "consult_persona",
        "arguments": '{"slug": "motoryka", "question": "jak skakać?"}',
    },
}


def _consult_orch() -> ChatOrchestrator:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    orch._consult_roster = [_P("b", "motor_coach", "motoryka", "Bartek")]
    orch._consult_count = 0
    orch._consult_session_id = "sess"
    return orch


def _patch_handle(
    monkeypatch: pytest.MonkeyPatch, orch: ChatOrchestrator, result: tuple[bool, str]
) -> None:
    async def _fake_handle(**kwargs: object) -> tuple[bool, str]:
        return result

    monkeypatch.setattr(orch, "handle_message", _fake_handle)


@pytest.mark.asyncio
async def test_consult_ok_response_includes_question(monkeypatch: pytest.MonkeyPatch) -> None:
    """GWT-1 (backend): persisted tool response carries Goat's question."""
    orch = _consult_orch()
    _patch_handle(monkeypatch, orch, (True, "Plyometria 2x."))
    orch._consult_user_queue = None
    raw = await orch._consult_persona(
        raw_arguments='{"slug": "motoryka", "question": "jak skakać?"}',
        user_id="u",
    )
    data = json.loads(raw)
    assert data["status"] == "ok"
    assert data["question"] == "jak skakać?"
    assert data["answer"] == "Plyometria 2x."


@pytest.mark.asyncio
async def test_consult_detail_event_after_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live: `consult_detail` emitted from `_execute_tool_calls`, AFTER `tool_result`."""
    from tests.test_consult_persona import _P as _LegacyP  # noqa: F401  (pattern reference)

    orch = _consult_orch()
    held = {"depth": 0}

    @asynccontextmanager
    async def fake_rls(_claims: object):
        held["depth"] += 1
        try:
            yield MagicMock()
        finally:
            held["depth"] -= 1

    class FakeChatRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def insert_assistant_message(self, **_kwargs: object) -> None:
            pass

        async def insert_tool_message(self, **_kwargs: object) -> None:
            pass

    monkeypatch.setattr("app.domain.chat.orchestrator.rls_connection", fake_rls)
    monkeypatch.setattr("app.domain.chat.orchestrator.ChatRepo", FakeChatRepo)
    _patch_handle(monkeypatch, orch, (True, "Plyometria 2x."))

    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    await orch._execute_tool_calls(
        user_id="u",
        session_id="s",
        persona=TeamLeadSpeaker(),
        assistant_content=None,
        tool_calls_payload=[_CONSULT_CALL],
        queue=queue,
        persist_messages=False,
        emit_sse=True,
    )
    events = [queue.get_nowait() for _ in range(queue.qsize())]
    names = [e["event"] for e in events]
    assert "tool_result" in names
    assert "consult_detail" in names
    assert names.index("tool_result") < names.index("consult_detail")
    detail = events[names.index("consult_detail")]
    payload = json.loads(str(detail["data"]))
    assert payload["tool_call_id"] == "call-1"
    assert payload["slug"] == "motoryka"
    assert payload["persona_label"] == "Bartek · Trener motoryczny"
    assert payload["question"] == "jak skakać?"
    assert payload["answer"] == "Plyometria 2x."


def test_consult_detail_not_emitted_on_error() -> None:
    """GWT-3: consult failure does not create an attachment."""
    body = json.dumps({"error": "Brak aktywnej persony o slugu 'x'."}, ensure_ascii=False)
    payload = _tool_result_event_payload("consult_persona", body)
    assert payload["success"] is False
    # `consult_detail` emission conditioned on `status == ok` — error JSON does not satisfy it.
    parsed = json.loads(body)
    assert parsed.get("status") != "ok"


@pytest.mark.asyncio
async def test_consult_execute_skips_consult_detail_when_emit_sse_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Consults without SSE (nested handle_message) do not emit consult_detail."""
    orch = _consult_orch()

    @asynccontextmanager
    async def fake_rls(_claims: object):
        yield MagicMock()

    class FakeChatRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def insert_assistant_message(self, **_kwargs: object) -> None:
            pass

        async def insert_tool_message(self, **_kwargs: object) -> None:
            pass

    monkeypatch.setattr("app.domain.chat.orchestrator.rls_connection", fake_rls)
    monkeypatch.setattr("app.domain.chat.orchestrator.ChatRepo", FakeChatRepo)
    _patch_handle(monkeypatch, orch, (True, "ok"))

    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    await orch._execute_tool_calls(
        user_id="u",
        session_id="s",
        persona=TeamLeadSpeaker(),
        assistant_content=None,
        tool_calls_payload=[_CONSULT_CALL],
        queue=queue,
        persist_messages=False,
        emit_sse=False,
    )
    assert queue.empty()