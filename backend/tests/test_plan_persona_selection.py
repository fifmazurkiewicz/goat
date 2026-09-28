"""Regression coverage for selected personas reaching plan generation."""

from contextlib import asynccontextmanager, nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.domain.plans import orchestrator as module


@pytest.mark.parametrize("persona_ids", [None, ["coach-2"]])
async def test_generate_plan_forwards_persona_selection(monkeypatch, persona_ids):
    planner = module.PlanOrchestrator(Mock())
    run = AsyncMock()
    monkeypatch.setattr(planner, "_run", run)
    monkeypatch.setattr(module, "observe", lambda **kwargs: nullcontext())
    monkeypatch.setattr(module, "update_observation", Mock())

    await planner.generate_plan(plan_id="plan", job_id="job", user_id="user", claims={}, persona_ids=persona_ids)

    run.assert_awaited_once_with(
        plan_id="plan", job_id="job", user_id="user", claims={}, user_brief=None, persona_ids=persona_ids
    )


@pytest.mark.parametrize(("persona_ids", "expected_ids"), [(None, ["coach-1", "coach-2"]), (["coach-2"], ["coach-2"])])
async def test_run_selects_personas_before_reserving_budget(monkeypatch, persona_ids, expected_ids):
    @asynccontextmanager
    async def connection(claims):
        yield Mock()

    class ReachedBudgetReservation(Exception):
        pass

    plans = AsyncMock()
    plans.list_job_personas.return_value = []
    personas = AsyncMock()
    personas.list_active_for_user.return_value = [
        SimpleNamespace(id=pid, type="custom", template_overrides={}, plan_template_id=None)
        for pid in ["coach-1", "coach-2"]
    ]
    monkeypatch.setattr(module, "rls_connection", connection)
    monkeypatch.setattr(module, "PlansRepo", lambda conn: plans)
    monkeypatch.setattr(module, "PersonasRepo", lambda conn: personas)
    monkeypatch.setattr(module, "ResultsRepo", lambda conn: AsyncMock())
    monkeypatch.setattr(module, "UserProfileRepo", lambda conn: AsyncMock())
    planner = module.PlanOrchestrator(Mock())
    reserve = AsyncMock(side_effect=ReachedBudgetReservation)
    monkeypatch.setattr(planner, "_reserve_budget", reserve)

    with pytest.raises(ReachedBudgetReservation):
        await planner._run(plan_id="plan", job_id="job", user_id="user", claims={}, persona_ids=persona_ids)

    plans.ensure_job_personas.assert_awaited_once_with("job", expected_ids)
    reserve.assert_awaited_once_with(claims={}, user_id="user", persona_count=len(expected_ids))
