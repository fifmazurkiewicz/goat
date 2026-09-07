"""Agent-hardening: cancel/resume, consult tools, rebuild confirm, usage, Goat overlay."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.domain.chat.orchestrator import ChatOrchestrator, _tool_result_event_payload
from app.domain.chat.plan_tools import (
    decide_rebuild_plan_action,
    tool_json_shows_rebuild_pending,
)
from app.domain.chat.preamble import TEAM_LEAD_SAFETY_OVERLAY, build_system_prompt
from app.domain.chat.team_lead import TeamLeadSpeaker, user_confirms_rebuild
from app.domain.chat.tools import get_consult_persona_tools, get_trainer_chat_tools
from app.domain.chat.turn_registry import should_conflict_chat_send
from app.domain.jobs.runner import STARTUP_RESUME_ORDER, select_jobs_to_resume
from app.domain.plans.orchestrator import should_finalize_plan_job_success
from app.domain.usage.service import UsageLimitService


def test_chat_hard_timeout_allows_goat_plus_consults() -> None:
    assert settings.chat_hard_timeout_s >= 180
    assert settings.chat_round_timeout_s >= 60
    assert settings.chat_hard_timeout_s > settings.chat_round_timeout_s


def test_should_not_finalize_success_after_cancel() -> None:
    assert should_finalize_plan_job_success("error") is False
    assert should_finalize_plan_job_success("cancelled") is False
    assert should_finalize_plan_job_success("success") is False
    assert should_finalize_plan_job_success("pending") is True
    assert should_finalize_plan_job_success("running") is True


def test_select_jobs_to_resume_includes_running() -> None:
    pending = MagicMock(status="pending", id="p1")
    running = MagicMock(status="running", id="r1")
    done = MagicMock(status="success", id="s1")
    selected = select_jobs_to_resume([pending, running, done])
    assert {j.id for j in selected} == {"p1", "r1"}


def test_consult_tools_are_read_only() -> None:
    names = {t["function"]["name"] for t in get_consult_persona_tools()}
    assert names == {"get_plan"}
    trainer = {t["function"]["name"] for t in get_trainer_chat_tools()}
    assert "log_result" in trainer
    assert "log_result" not in names
    assert "update_user_profile" not in names
    assert "upsert_plan_items" not in names


@pytest.mark.asyncio
async def test_consult_read_only_blocks_write_tools() -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    persona = MagicMock(type="motor_coach", id="p1")
    for name in ("log_result", "update_user_profile", "upsert_plan_items"):
        raw = await orch._run_single_tool(
            name=name,
            raw_arguments="{}",
            user_id="u",
            persona=persona,
            consult_read_only=True,
        )
        parsed = json.loads(raw)
        assert "error" in parsed
        assert "tylko do odczytu" in parsed["error"]


def test_user_confirms_rebuild_polish_yes() -> None:
    assert user_confirms_rebuild("tak")
    assert user_confirms_rebuild("Tak, przebuduj")
    assert user_confirms_rebuild("potwierdzam")
    assert not user_confirms_rebuild("zrób mi plan na tydzień")
    assert not user_confirms_rebuild("nie")


def test_rebuild_requires_confirm_when_no_job() -> None:
    decision = decide_rebuild_plan_action(confirmed=False, user_message="Przebuduj plan", active_job_id=None)
    assert decision["action"] == "needs_confirm"
    assert "Potwierdź przebudowę planu" in decision["message"]


def test_rebuild_ignores_model_confirmed_flag() -> None:
    decision = decide_rebuild_plan_action(confirmed=True, user_message="Przebuduj plan na tydzień", active_job_id=None)
    assert decision["action"] == "needs_confirm"


def test_rebuild_tak_without_pending_stays_confirm() -> None:
    decision = decide_rebuild_plan_action(
        confirmed=False, user_message="tak", active_job_id=None, rebuild_pending=False
    )
    assert decision["action"] == "needs_confirm"


def test_rebuild_enqueues_when_user_says_tak_after_pending() -> None:
    decision = decide_rebuild_plan_action(
        confirmed=False,
        user_message="tak",
        active_job_id=None,
        rebuild_pending=True,
    )
    assert decision["action"] == "enqueue"


def test_tool_json_shows_rebuild_pending_from_history() -> None:
    assert tool_json_shows_rebuild_pending(['{"status": "needs_confirm", "message": "Potwierdź przebudowę planu"}'])
    assert not tool_json_shows_rebuild_pending(
        [
            '{"status": "needs_confirm"}',
            '{"status": "ok", "job_id": "j1"}',
        ]
    )


def test_job_status_update_is_cas_on_active_rows() -> None:
    import inspect

    from app.repositories.plans_repo import PlansRepo

    source = inspect.getsource(PlansRepo.update_job_status)
    assert "status IN ('pending', 'running')" in source


def test_startup_resumes_pending_before_orphans() -> None:
    import inspect

    from app import main

    assert STARTUP_RESUME_ORDER == ("pending", "orphaned")
    source = inspect.getsource(main.lifespan)
    assert source.find("resume_pending_jobs_on_startup") < source.find("resume_orphaned_plan_jobs_on_startup")


def test_retry_conflicts_while_live_turn() -> None:
    assert should_conflict_chat_send(live_task=True, db_flag=True, retry=True) is True
    assert should_conflict_chat_send(live_task=True, db_flag=False, retry=True) is True
    assert should_conflict_chat_send(live_task=False, db_flag=True, retry=True) is False
    assert should_conflict_chat_send(live_task=False, db_flag=True, retry=False) is True
    assert should_conflict_chat_send(live_task=False, db_flag=False, retry=True) is False


def test_rebuild_returns_existing_job_when_in_flight() -> None:
    decision = decide_rebuild_plan_action(confirmed=True, user_message="tak", active_job_id="job-existing")
    assert decision["action"] == "reuse"
    assert decision["job_id"] == "job-existing"


def test_tool_result_rebuild_needs_confirm_copy() -> None:
    body = json.dumps(
        {"status": "needs_confirm", "message": "Potwierdź przebudowę planu"},
        ensure_ascii=False,
    )
    payload = _tool_result_event_payload("rebuild_plan", body)
    assert payload["success"] is False
    assert "Potwierdź przebudowę planu" in payload["summary"]
    assert payload.get("needs_confirm") is True


def test_goat_gets_trainer_style_safety_overlay() -> None:
    out = build_system_prompt(
        "Goat behavior.",
        template_safety_prompt=TEAM_LEAD_SAFETY_OVERLAY,
        persona_type="team_lead",
    )
    assert "Nie przepisujesz leków" in out
    assert "czerwon" in out.lower() or "samobój" in out.lower() or "kryzys" in out.lower()
    assert "ZABEZPIECZENIA GOTOWCA" in out


@pytest.mark.asyncio
async def test_reconcile_uses_reserved_usd_not_zero_prompt_recompute() -> None:
    from tests.test_usage_limit_service import _FakePricingCache, _FakeProfilesRepo, _FakeUsageRepo

    usage_repo = _FakeUsageRepo(budget=10.0)
    service = UsageLimitService(usage_repo, _FakeProfilesRepo(10.0), _FakePricingCache())
    reserved = 2.0
    period_start = await service.reserve_estimated_cost(user_id="u1", estimated_cost_usd=reserved)
    await service.reconcile_actual_cost(
        user_id="u1",
        period_start=period_start,
        estimated_cost_usd=reserved,
        actual_cost_usd=0.4,
    )
    assert usage_repo.row.cost_usd_used == pytest.approx(0.4)

    recomputed = await service.estimate_turn_cost_usd(model="test", prompt_text_length_chars=0, max_output_tokens=1500)
    assert recomputed != reserved


@pytest.mark.asyncio
async def test_consult_cap_increments_only_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    orch._consult_roster = [MagicMock(id="b", type="motor_coach", slug="motoryka", name="Bartek")]
    orch._consult_count = 0
    orch._consult_session_id = "sess"
    orch._consult_user_queue = None

    async def _fail(**_kwargs: object) -> tuple[bool, str | None]:
        return False, None

    monkeypatch.setattr(orch, "handle_message", _fail)
    raw = await orch._consult_persona(
        raw_arguments='{"slug": "motoryka", "question": "jak skakać?"}',
        user_id="u",
    )
    assert "error" in json.loads(raw)
    assert orch._consult_count == 0


@pytest.mark.asyncio
async def test_consult_handle_message_uses_read_only_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    motor = MagicMock(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    orch._consult_roster = [motor]
    orch._consult_count = 0
    orch._consult_session_id = "sess"
    orch._consult_user_queue = None
    seen: dict[str, Any] = {}

    async def _fake_handle(**kwargs: object) -> tuple[bool, str]:
        seen.update(kwargs)
        return True, "ok"

    monkeypatch.setattr(orch, "handle_message", _fake_handle)
    await orch._consult_persona(
        raw_arguments='{"slug": "motoryka", "question": "q"}',
        user_id="u",
    )
    assert seen.get("consult_read_only") is True
    assert orch._consult_count == 1


@pytest.mark.asyncio
async def test_execute_tool_calls_persists_assistant_and_tools_in_one_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = ChatOrchestrator(MagicMock(), claims={"sub": "u"})
    timeline: list[str] = []
    conn_ids: list[int] = []

    @asynccontextmanager
    async def fake_rls(_claims: object):
        conn = MagicMock()
        conn_ids.append(id(conn))
        timeline.append("conn_enter")
        try:
            yield conn
        finally:
            timeline.append("conn_exit")

    class FakeChatRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def insert_assistant_message(self, **_kwargs: object) -> None:
            timeline.append("insert_assistant")

        async def insert_tool_message(self, **_kwargs: object) -> None:
            timeline.append("insert_tool")

    async def fake_consult(*, raw_arguments: str, user_id: str, **_kwargs: object) -> str:
        timeline.append("consult")
        return json.dumps(
            {"status": "ok", "slug": "motoryka", "persona_label": "Bartek", "answer": "ok"},
            ensure_ascii=False,
        )

    monkeypatch.setattr("app.domain.chat.orchestrator.rls_connection", fake_rls)
    monkeypatch.setattr("app.domain.chat.orchestrator.ChatRepo", FakeChatRepo)
    monkeypatch.setattr(orch, "_consult_persona", fake_consult)

    queue: Any = __import__("asyncio").Queue()
    await orch._execute_tool_calls(
        user_id="u",
        session_id="s",
        persona=TeamLeadSpeaker(),
        assistant_content="treść",
        tool_calls_payload=[
            {
                "id": "c1",
                "type": "function",
                "function": {
                    "name": "consult_persona",
                    "arguments": '{"slug": "motoryka", "question": "q"}',
                },
            }
        ],
        queue=queue,
        persist_messages=True,
        emit_sse=False,
    )

    consult_at = timeline.index("consult")
    persist = timeline[consult_at + 1 :]
    assert persist[:4] == ["conn_enter", "insert_assistant", "insert_tool", "conn_exit"]
    assert timeline.count("conn_enter") == 1
