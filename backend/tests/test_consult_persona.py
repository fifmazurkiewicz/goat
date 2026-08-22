"""Task 3 — consult_persona w orkiestratorze (emit_sse / persist_messages)."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AppError
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
    assert "motoryka" in payload["error"]
    assert "Nieznane narzędzie" not in payload["error"]


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
    payload = json.loads(raw)
    assert "error" in payload
    assert "5" in payload["error"]
    assert "Nieznane narzędzie" not in payload["error"]


@pytest.mark.asyncio
async def test_trainer_blocked_from_consult_persona() -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    trainer = _P(id="a", type="dietitian", slug="dietetyk")
    raw = await orch._run_single_tool(
        name="consult_persona",
        raw_arguments='{"slug": "dietetyk", "question": "x"}',
        user_id="u",
        persona=trainer,
        results_service=MagicMock(),
        user_profile_repo=MagicMock(),
        plan_tools=MagicMock(),
    )
    payload = json.loads(raw)
    assert "error" in payload
    assert "Goat" in payload["error"]
    assert "Nieznane narzędzie" not in payload["error"]


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


@pytest.mark.asyncio
async def test_consult_happy_path_returns_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    motor = _P(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    orch._consult_roster = [motor]
    orch._consult_count = 0
    orch._consult_session_id = "sess"
    orch._consult_user_queue = None

    async def _fake_handle(**kwargs: object) -> tuple[bool, str]:
        assert kwargs["persona"].slug == "motoryka"  # type: ignore[union-attr]
        assert kwargs["client_visible"] is False
        assert kwargs["persist_messages"] is False
        assert kwargs["emit_sse"] is False
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


@pytest.mark.asyncio
async def test_consult_emits_goat_status_on_user_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    motor = _P(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    orch._consult_roster = [motor]
    orch._consult_count = 0
    orch._consult_session_id = "sess"
    user_queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    orch._consult_user_queue = user_queue

    async def _fake_handle(**kwargs: object) -> tuple[bool, str]:
        return True, "ok"

    monkeypatch.setattr(orch, "handle_message", _fake_handle)
    await orch._consult_persona(
        raw_arguments='{"slug": "motoryka", "question": "jak skakać?"}',
        user_id="u",
    )
    event = user_queue.get_nowait()
    assert event["event"] == "persona_status"
    payload = json.loads(event["data"])
    assert payload["message"] == "Goat konsultuje z Bartek · Trener motoryczny…"
    assert payload["tool_name"] == "consult_persona"


_CONSULT_CALL = {
    "id": "c1",
    "type": "function",
    "function": {
        "name": "consult_persona",
        "arguments": '{"slug": "motoryka", "question": "q"}',
    },
}


@pytest.mark.asyncio
async def test_consult_persona_runs_outside_parent_rls_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    held = {"depth": 0}
    timeline: list[str] = []

    @asynccontextmanager
    async def fake_rls(_claims: object):
        held["depth"] += 1
        timeline.append("conn_enter")
        try:
            yield MagicMock()
        finally:
            timeline.append("conn_exit")
            held["depth"] -= 1

    class FakeChatRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def insert_assistant_message(self, **_kwargs: object) -> None:
            timeline.append("insert_assistant")

        async def insert_tool_message(self, **_kwargs: object) -> None:
            timeline.append("insert_tool")

    async def fake_consult(*, raw_arguments: str, user_id: str, **_kwargs: object) -> str:
        timeline.append("consult")
        assert held["depth"] == 0
        return json.dumps(
            {"status": "ok", "slug": "motoryka", "persona_label": "Bartek", "answer": "ok"},
            ensure_ascii=False,
        )

    monkeypatch.setattr("app.domain.chat.orchestrator.rls_connection", fake_rls)
    monkeypatch.setattr("app.domain.chat.orchestrator.ChatRepo", FakeChatRepo)
    monkeypatch.setattr(orch, "_consult_persona", fake_consult)

    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    await orch._execute_tool_calls(
        user_id="u",
        session_id="s",
        persona=TeamLeadSpeaker(),
        assistant_content=" treść ",
        tool_calls_payload=[_CONSULT_CALL],
        queue=queue,
        persist_messages=True,
        emit_sse=True,
    )

    consult_at = timeline.index("consult")
    assert "conn_enter" not in timeline[consult_at:] or timeline[consult_at - 1] == "conn_exit"
    assert held["depth"] == 0
    assert timeline.count("insert_assistant") == 1
    assert timeline.count("insert_tool") == 1
    assert timeline.index("insert_assistant") < consult_at < timeline.index("insert_tool")
    event = queue.get_nowait()
    assert event["event"] == "tool_result"


@pytest.mark.asyncio
async def test_consult_execute_skips_persist_and_sse_when_flags_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    held = {"depth": 0}
    inserts = {"assistant": 0, "tool": 0}

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
            inserts["assistant"] += 1

        async def insert_tool_message(self, **_kwargs: object) -> None:
            inserts["tool"] += 1

    async def fake_consult(*, raw_arguments: str, user_id: str, **_kwargs: object) -> str:
        assert held["depth"] == 0
        return json.dumps({"status": "ok", "slug": "x", "persona_label": "X", "answer": "a"})

    monkeypatch.setattr("app.domain.chat.orchestrator.rls_connection", fake_rls)
    monkeypatch.setattr("app.domain.chat.orchestrator.ChatRepo", FakeChatRepo)
    monkeypatch.setattr(orch, "_consult_persona", fake_consult)

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
    assert inserts == {"assistant": 0, "tool": 0}
    assert queue.empty()


@pytest.mark.asyncio
async def test_handle_message_errors_skip_sse_when_emit_sse_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})

    async def _boom(**_kwargs: object) -> tuple[bool, str | None]:
        raise AppError("nope")

    monkeypatch.setattr(orch, "_handle_message_inner", _boom)
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    ok, answer = await orch.handle_message(
        user_id="u",
        session_id="s",
        session_type="general",
        persona=TeamLeadSpeaker(),
        user_message="hi",
        queue=queue,
        emit_sse=False,
    )
    assert ok is False
    assert answer is None
    assert queue.empty()
