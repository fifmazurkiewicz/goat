"""`/plans` router — generation and reading of plans (3-stage pipeline, `BackgroundTasks`).

See docs/technical/architecture.md section 4 (pipeline, job state model) and
docs/adr/decisions.md ADR-1/ADR-2. Orchestration in
`app/domain/plans/orchestrator.py::PlanOrchestrator`.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.db import rls_connection, service_role_connection
from app.core.security import AuthContext, get_current_user
from app.domain.jobs.job_registry import cancel_job
from app.domain.jobs.runner import enqueue_plan_generation_async
from app.models.schemas import (
    PlanGenerateRequest,
    PlanGenerationJobOut,
    PlanGenerationJobPersonaOut,
    PlanItemOut,
    PlanOut,
    PlanRangeOut,
    PlanSummaryOut,
)
from app.repositories.plans_repo import PlanJobRow, PlanRow, PlansRepo

router = APIRouter(prefix="/plans", tags=["plans"])


def _period_end_date(period_type: str, start_date: date) -> date:
    """ASSUMPTION (docs don't specify the `end_date` formula directly): 'week' -> 7-day
    range from `start_date` (inclusive), 'month' -> to the last calendar day of the
    month CONTAINING `start_date` (not "30 days from start")."""
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


def _plan_summary(plan: PlanRow) -> PlanSummaryOut:
    return PlanSummaryOut(
        id=plan.id,
        user_id=plan.user_id,
        period_type=plan.period_type,
        start_date=plan.start_date,
        end_date=plan.end_date,
        status=plan.status,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
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
    """Creates `plans`+`plan_generation_jobs` (status `generating`/`pending`) and queues
    generation in the background (`BackgroundTasks` — no separate Render Worker, ADR-1).
    The frontend polls `GET /plans/jobs/{id}` for the `job_id` returned here."""
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

    await enqueue_plan_generation_async(
        plan_id=plan.id,
        plan_job_id=job.id,
        user_id=auth.user_id,
        claims=auth.claims,
        background_tasks=background_tasks,
    )
    return _job_row_to_out(job, [])


async def _cancel_plan_background_tasks(plan_job_id: str) -> None:
    """Marks the related `background_jobs` row (migration 0008) as cancelled."""
    from sqlalchemy import text

    try:
        async with service_role_connection() as conn:
            await conn.execute(
                text(
                    """
                    UPDATE background_jobs
                    SET status = 'error',
                        error_message = 'Anulowano przez użytkownika.',
                        finished_at = now()
                    WHERE job_type = 'plan_generate'
                      AND payload->>'plan_job_id' = :plan_job_id
                      AND status IN ('pending', 'running')
                    """
                ),
                {"plan_job_id": plan_job_id},
            )
    except ProgrammingError:
        pass


@router.get("/jobs/active", response_model=PlanGenerationJobOut | None)
async def get_active_plan_job(auth: AuthContext = Depends(get_current_user)) -> PlanGenerationJobOut | None:
    """User's active plan generation job (`pending`/`running`) — for UI sync on refresh."""
    async with rls_connection(auth.claims) as conn:
        plans_repo = PlansRepo(conn)
        job = await plans_repo.get_active_job_for_user(auth.user_id)
        if job is None:
            return None
        personas = await plans_repo.list_job_personas(job.id)
    return _job_row_to_out(job, [PlanGenerationJobPersonaOut.model_validate(p) for p in personas])


@router.post("/jobs/{job_id}/cancel", response_model=PlanGenerationJobOut)
async def cancel_plan_job(job_id: str, auth: AuthContext = Depends(get_current_user)) -> PlanGenerationJobOut:
    """Cancels the active job — frees the `one_active_job_per_user` slot, plan -> `error`."""
    async with rls_connection(auth.claims) as conn:
        job = await PlansRepo(conn).cancel_job(job_id)
    cancel_job(job_id)
    await _cancel_plan_background_tasks(job_id)
    async with rls_connection(auth.claims) as conn:
        personas = await PlansRepo(conn).list_job_personas(job_id)
    return _job_row_to_out(job, [PlanGenerationJobPersonaOut.model_validate(p) for p in personas])


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


@router.get("", response_model=PlanRangeOut)
@router.get("/", response_model=PlanRangeOut, include_in_schema=False)
async def get_plan_range(
    start_date: date = Query(..., description="Początek widocznego zakresu kalendarza (YYYY-MM-DD)."),
    end_date: date = Query(..., description="Koniec widocznego zakresu kalendarza (YYYY-MM-DD)."),
    auth: AuthContext = Depends(get_current_user),
) -> PlanRangeOut:
    """`GET /plans?start_date=&end_date=` — plan metadata + items in the view range."""
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    async with rls_connection(auth.claims) as conn:
        plans_repo = PlansRepo(conn)
        plan = await plans_repo.pick_plan_for_range(range_start=start_date, range_end=end_date)
        if plan is None:
            return PlanRangeOut(plan=None, items=[])

        all_items = await plans_repo.list_items_for_plan(plan.id)
        filtered = [
            PlanItemOut.model_validate(item)
            for item in all_items
            if start_date <= item.item_date <= end_date
        ]
        return PlanRangeOut(plan=_plan_summary(plan), items=filtered)
