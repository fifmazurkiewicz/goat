"""Chat rebuild confirmation, committed job inputs, and worker dispatch."""

import json
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.domain.chat import plan_tools
from app.domain.jobs import runner
from app.repositories.chat_repo import ChatRepo


@pytest.mark.parametrize("confirmed", [False, True])
async def test_chat_rebuild_requires_user_confirmation(monkeypatch, confirmed):
    repo = AsyncMock()
    repo.get_active_job_for_user.return_value = None
    monkeypatch.setattr(plan_tools, "PlansRepo", lambda conn: repo)
    enqueue = AsyncMock()
    monkeypatch.setattr(plan_tools, "enqueue_plan_generation_async", enqueue)

    result = await plan_tools.ChatPlanToolsService(Mock(), claims={}).rebuild_plan(
        user_id="user",
        period_type="week",
        start_date=date(2026, 9, 28),
        user_message="Ułóż plan na tydzień",
        confirmed=confirmed,
    )

    assert result["status"] == "needs_confirm"
    repo.create_plan.assert_not_awaited()
    enqueue.assert_not_awaited()


async def test_confirmed_chat_rebuild_commits_before_worker_dispatch(monkeypatch):
    claims = {"sub": "user"}
    outer_conn, job_conn = Mock(), Mock()
    read_repo, write_repo = AsyncMock(), AsyncMock()
    read_repo.get_active_job_for_user.return_value = None
    write_repo.create_plan.return_value = SimpleNamespace(id="plan")
    write_repo.create_job.return_value = SimpleNamespace(id="job")
    committed = False

    @asynccontextmanager
    async def connection(received_claims):
        nonlocal committed
        assert received_claims == claims
        yield job_conn
        committed = True

    monkeypatch.setattr(plan_tools, "rls_connection", connection)
    monkeypatch.setattr(plan_tools, "PlansRepo", lambda conn: write_repo if conn is job_conn else read_repo)
    history = AsyncMock(return_value=[SimpleNamespace(role="tool", content='{"status":"needs_confirm"}')])
    monkeypatch.setattr(ChatRepo, "list_recent_messages_for_context", history)
    planner = Mock(generate_plan=AsyncMock())
    monkeypatch.setattr(runner, "PlanOrchestrator", lambda client: planner)
    monkeypatch.setattr(runner, "get_openrouter_client", Mock())

    async def enqueue(**kwargs):
        assert committed, "The worker must see committed plan/job records"
        await runner._dispatch(
            job_type=kwargs["job_type"],
            user_id=kwargs["user_id"],
            claims=kwargs["claims"],
            payload=kwargs["payload"],
        )
        return "background-job"

    monkeypatch.setattr(runner, "enqueue_background_job", enqueue)
    result = await plan_tools.ChatPlanToolsService(outer_conn, claims=claims).rebuild_plan(
        user_id="user",
        period_type="week",
        start_date=date(2026, 9, 28),
        user_message="tak",
        session_id="session",
        user_brief="Bez badmintona",
    )

    assert result["status"] == "ok"
    assert result["job_id"] == "job"
    assert result["background_job_id"] == "background-job"
    write_repo.create_plan.assert_awaited_once_with(
        user_id="user",
        period_type="week",
        start_date=date(2026, 9, 28),
        end_date=date(2026, 10, 4),
    )
    write_repo.create_job.assert_awaited_once_with(plan_id="plan", user_id="user")
    planner.generate_plan.assert_awaited_once_with(
        plan_id="plan",
        job_id="job",
        user_id="user",
        claims=claims,
        user_brief="Bez badmintona",
        persona_ids=None,
    )
    from app.domain.chat.orchestrator import _tool_result_event_payload

    event = _tool_result_event_payload("rebuild_plan", json.dumps(result))
    assert event["success"] is True
    assert event["job_id"] == "job"
