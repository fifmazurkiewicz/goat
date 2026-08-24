"""Uniform enqueue of background jobs — plan_generate, plan_harmonize, chat_title."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import BackgroundTasks
from sqlalchemy.exc import ProgrammingError

from app.core.config import settings
from app.core.db import rls_connection, service_role_connection
from app.domain.chat.title_service import ChatTitleService
from app.domain.plans.orchestrator import PlanOrchestrator
from app.llm.openrouter_client import get_openrouter_client
from app.repositories.background_jobs_repo import BackgroundJobsRepo

logger = structlog.get_logger(__name__)


async def _run_job_wrapper(*, bg_job_id: str, claims: dict[str, Any], coro) -> None:
    try:
        async with service_role_connection() as conn:
            await BackgroundJobsRepo(conn).mark_running(bg_job_id)
        await coro
        async with service_role_connection() as conn:
            await BackgroundJobsRepo(conn).mark_finished(bg_job_id, status="success")
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("background_job_failed", bg_job_id=bg_job_id, error=str(exc), exc_info=exc)
        async with service_role_connection() as conn:
            await BackgroundJobsRepo(conn).mark_finished(
                bg_job_id, status="error", error_message=str(exc)[:500]
            )


async def enqueue_background_job(
    *,
    job_type: str,
    user_id: str,
    claims: dict[str, Any],
    payload: dict[str, Any],
    background_tasks: BackgroundTasks | None = None,
) -> str:
    async with rls_connection(claims) as conn:
        row = await BackgroundJobsRepo(conn).create(
            user_id=user_id, job_type=job_type, payload=payload
        )

    coro = _dispatch(job_type=job_type, user_id=user_id, claims=claims, payload=payload)
    runner = _run_job_wrapper(bg_job_id=row.id, claims=claims, coro=coro)

    # Always asyncio.create_task — BackgroundTasks on Render/some hosts doesn't
    # guarantee execution after 202 (the job stays `pending` forever).
    asyncio.create_task(runner)

    return row.id


async def _dispatch(
    *, job_type: str, user_id: str, claims: dict[str, Any], payload: dict[str, Any]
) -> None:
    if job_type == "plan_generate":
        orchestrator = PlanOrchestrator(get_openrouter_client())
        await orchestrator.generate_plan(
            plan_id=str(payload["plan_id"]),
            job_id=str(payload["plan_job_id"]),
            user_id=user_id,
            claims=claims,
            user_brief=str(payload["user_brief"]).strip() if payload.get("user_brief") else None,
        )
        return

    if job_type == "plan_harmonize":
        orchestrator = PlanOrchestrator(get_openrouter_client())
        await orchestrator.run_harmonize_for_dates(
            plan_id=str(payload["plan_id"]),
            user_id=user_id,
            claims=claims,
            dates=[str(d) for d in payload.get("dates") or []],
        )
        return

    if job_type == "chat_title":
        await ChatTitleService(get_openrouter_client()).generate_and_set_title(
            session_id=str(payload["session_id"]),
            user_message=str(payload["message"]),
            claims=claims,
        )
        return

    raise ValueError(f"Nieznany job_type: {job_type!r}")


async def enqueue_plan_generation_async(
    *,
    plan_id: str,
    plan_job_id: str,
    user_id: str,
    claims: dict[str, Any],
    background_tasks: BackgroundTasks | None = None,
    user_brief: str | None = None,
) -> str:
    payload: dict[str, Any] = {"plan_id": plan_id, "plan_job_id": plan_job_id}
    if user_brief and user_brief.strip():
        payload["user_brief"] = user_brief.strip()[:2000]
    return await enqueue_background_job(
        job_type="plan_generate",
        user_id=user_id,
        claims=claims,
        payload=payload,
        background_tasks=background_tasks,
    )


async def enqueue_plan_harmonize_async(
    *,
    plan_id: str,
    user_id: str,
    claims: dict[str, Any],
    dates: list[str],
) -> str | None:
    if not settings.plan_auto_harmonize_on_upsert or not dates:
        return None
    return await enqueue_background_job(
        job_type="plan_harmonize",
        user_id=user_id,
        claims=claims,
        payload={"plan_id": plan_id, "dates": dates},
        background_tasks=None,
    )


async def enqueue_chat_title_async(
    *,
    session_id: str,
    user_id: str,
    claims: dict[str, Any],
    message: str,
) -> str | None:
    if not settings.chat_llm_title_enabled:
        return None
    return await enqueue_background_job(
        job_type="chat_title",
        user_id=user_id,
        claims=claims,
        payload={"session_id": session_id, "message": message[:500]},
        background_tasks=None,
    )


async def resume_orphaned_plan_jobs_on_startup() -> None:
    """Resumes `plan_generation_jobs` pending/running with no active `background_jobs` entry."""
    from sqlalchemy import text

    try:
        async with service_role_connection() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT pgj.id, pgj.plan_id, pgj.user_id
                    FROM plan_generation_jobs pgj
                    WHERE pgj.status IN ('pending', 'running')
                      AND NOT EXISTS (
                        SELECT 1 FROM background_jobs bj
                        WHERE bj.job_type = 'plan_generate'
                          AND bj.payload->>'plan_job_id' = pgj.id::text
                          AND bj.status IN ('pending', 'running')
                      )
                    ORDER BY pgj.created_at ASC
                    LIMIT 5
                    """
                )
            )
            rows = list(result)
    except ProgrammingError as exc:
        logger.warning("orphaned_plan_jobs_startup_skipped", error=str(exc))
        return

    for row in rows:
        user_id = str(row.user_id)
        plan_job_id = str(row.id)
        plan_id = str(row.plan_id)
        logger.info("orphaned_plan_job_resuming", plan_job_id=plan_job_id, plan_id=plan_id)
        await enqueue_background_job(
            job_type="plan_generate",
            user_id=user_id,
            claims={"sub": user_id},
            payload={"plan_id": plan_id, "plan_job_id": plan_job_id},
            background_tasks=None,
        )


async def resume_pending_jobs_on_startup() -> None:
    try:
        async with service_role_connection() as conn:
            repo = BackgroundJobsRepo(conn)
            reaped = await repo.reap_stale_running(older_than_minutes=settings.plan_reaper_stale_minutes)
            if reaped:
                logger.warning("background_jobs_reaped", job_ids=reaped, count=len(reaped))
            pending = await repo.list_resumable(limit=10)
    except ProgrammingError as exc:
        logger.warning(
            "background_jobs_startup_skipped",
            error=str(exc),
            hint="Uruchom migrację supabase/migrations/0008_background_jobs.sql",
        )
        return

    for job in pending:
        if job.status == "running":
            continue
        logger.info("background_job_resuming", bg_job_id=job.id, job_type=job.job_type)
        claims = {"sub": job.user_id}
        asyncio.create_task(
            _run_job_wrapper(
                bg_job_id=job.id,
                claims=claims,
                coro=_dispatch(
                    job_type=job.job_type,
                    user_id=job.user_id,
                    claims=claims,
                    payload=job.payload,
                ),
            )
        )
