"""Router `/plans` — generowanie i odczyt planów (pipeline 3-etapowy, `BackgroundTasks`).

Patrz docs/technical/architecture.md sekcja 4 (pipeline, model stanu jobów) i
docs/adr/decisions.md ADR-1/ADR-2. Orkiestracja w
`app/domain/plans/orchestrator.py::PlanOrchestrator`.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.db import rls_connection
from app.core.security import AuthContext, get_current_user
from app.domain.plans.orchestrator import PlanOrchestrator
from app.llm.openrouter_client import get_openrouter_client
from app.models.schemas import (
    PlanGenerateRequest,
    PlanGenerationJobOut,
    PlanGenerationJobPersonaOut,
    PlanItemOut,
    PlanOut,
)
from app.repositories.plans_repo import PlanJobRow, PlanRow, PlansRepo

router = APIRouter(prefix="/plans", tags=["plans"])


def _period_end_date(period_type: str, start_date: date) -> date:
    """ZAŁOŻENIE (dokumentacja nie precyzuje formuły `end_date` wprost): 'week' -> 7-dniowy
    zakres od `start_date` (włącznie), 'month' -> do ostatniego dnia kalendarzowego
    miesiąca ZAWIERAJĄCEGO `start_date` (nie "30 dni od startu")."""
    if period_type == "week":
        return start_date + timedelta(days=6)
    last_day = calendar.monthrange(start_date.year, start_date.month)[1]
    return start_date.replace(day=last_day)


def _job_row_to_out(job: PlanJobRow, personas: list[PlanGenerationJobPersonaOut]) -> PlanGenerationJobOut:
    return PlanGenerationJobOut(
        id=job.id,
        plan_id=job.plan_id,
        status=job.status,
        error_message=job.error_message,
        attempts=job.attempts,
        personas=personas,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


async def _plan_out_with_items(conn: AsyncConnection, plan: PlanRow) -> PlanOut:
    items = await PlansRepo(conn).list_items_for_plan(plan.id)
    return PlanOut(
        id=plan.id,
        user_id=plan.user_id,
        period_type=plan.period_type,
        start_date=plan.start_date,
        end_date=plan.end_date,
        status=plan.status,
        items=[PlanItemOut.model_validate(item) for item in items],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.post("/generate", response_model=PlanGenerationJobOut, status_code=202)
async def generate_plan(
    payload: PlanGenerateRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(get_current_user),
) -> PlanGenerationJobOut:
    """Tworzy `plans`+`plan_generation_jobs` (status `generating`/`pending`) i kolejkuje
    generowanie w tle (`BackgroundTasks` — bez osobnego Render Workera, ADR-1). Frontend
    polluje `GET /plans/jobs/{id}` po `job_id` zwróconym tutaj."""
    end_date = _period_end_date(payload.period_type, payload.start_date)

    async with rls_connection(auth.claims) as conn:
        plans_repo = PlansRepo(conn)
        plan = await plans_repo.create_plan(
            user_id=auth.user_id,
            period_type=payload.period_type,
            start_date=payload.start_date,
            end_date=end_date,
        )
        job = await plans_repo.create_job(plan_id=plan.id, user_id=auth.user_id)

    orchestrator = PlanOrchestrator(get_openrouter_client())
    background_tasks.add_task(
        orchestrator.generate_plan,
        plan_id=plan.id,
        job_id=job.id,
        user_id=auth.user_id,
        claims=auth.claims,
    )
    return _job_row_to_out(job, [])


@router.get("/jobs/{job_id}", response_model=PlanGenerationJobOut)
async def get_plan_job(job_id: str, auth: AuthContext = Depends(get_current_user)) -> PlanGenerationJobOut:
    async with rls_connection(auth.claims) as conn:
        plans_repo = PlansRepo(conn)
        job = await plans_repo.get_job_or_raise(job_id)
        personas = await plans_repo.list_job_personas(job_id)
    return _job_row_to_out(job, [PlanGenerationJobPersonaOut.model_validate(p) for p in personas])


@router.get("/{target_date}", response_model=PlanOut | None)
async def get_plan_for_date(
    target_date: date, auth: AuthContext = Depends(get_current_user)
) -> PlanOut | None:
    async with rls_connection(auth.claims) as conn:
        plan = await PlansRepo(conn).get_plan_for_date(target_date)
        if plan is None:
            return None
        return await _plan_out_with_items(conn, plan)


@router.get("", response_model=list[PlanOut])
@router.get("/", response_model=list[PlanOut], include_in_schema=False)
async def list_plans(
    month: date = Query(..., description="Dowolna data w interesującym miesiącu (YYYY-MM-DD)."),
    auth: AuthContext = Depends(get_current_user),
) -> list[PlanOut]:
    """`GET /plans?month=YYYY-MM-DD` — wszystkie plany nachodzące na kalendarzowy miesiąc
    zawierający podaną datę."""
    range_start = month.replace(day=1)
    last_day = calendar.monthrange(month.year, month.month)[1]
    range_end = month.replace(day=last_day)

    async with rls_connection(auth.claims) as conn:
        plans = await PlansRepo(conn).list_plans_overlapping(range_start=range_start, range_end=range_end)
        return [await _plan_out_with_items(conn, plan) for plan in plans]
