"""FastAPI application entry point — Multi-Persona Coaching App backend.

Structure follows docs/technical/architecture.md section 1: routers under `/api/v1`
(health outside this prefix, see devops.md — Render Health Check = `/api/health`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routers import (
    account,
    admin,
    auth,
    chat,
    exercises,
    health,
    personas,
    plans,
    profile,
    results,
    templates,
    usage,
)
from app.core.config import settings
from app.core.db import service_role_connection
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIDMiddleware, configure_logging
from app.domain.jobs.runner import (
    clear_orphaned_turns_on_startup,
    resume_orphaned_plan_jobs_on_startup,
    resume_pending_jobs_on_startup,
)
from app.domain.results.metrics_cache import allowed_metrics_cache
from app.repositories.allowed_metrics_repo import AllowedMetricsRepo

configure_logging(settings.environment)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("starting_up", environment=settings.environment)

    # Resume pending|running jobs after Render restart (do not reap them as error).
    # `service_role` because startup operates on ALL users, not one RLS context.
    async with service_role_connection() as conn:
        # `allowed_metrics` — in-memory cache, hot path during `log_result` on the SSE
        # stream (we don't want an SQL query per tool call).
        await allowed_metrics_cache.load(AllowedMetricsRepo(conn))

    await clear_orphaned_turns_on_startup()
    # Pending background_jobs first — then orphans without a bg row. Reverse order
    # double-starts the same plan_job (orphan enqueue + resume of that new row).
    await resume_pending_jobs_on_startup()
    await resume_orphaned_plan_jobs_on_startup()

    yield
    logger.info("shutting_down")


app = FastAPI(
    title="Multi-Persona Coaching App API",
    version="0.1.0",
    lifespan=lifespan,
)

# Explicit allowlist (docs/technical/security.md section 5) + regex for custom domain
# and Vercel preview — NEVER wildcard "*", especially with the Authorization header.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https://([a-z0-9-]+\.)?fmazurkiewicz\.dev$|https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)

# Last added = outermost — compresses all responses (exercise catalog ~0.7 MB JSON
# after free-exercise-db import). Smoke test of the SSE stream after deploy: gzip also
# wraps the chat; if it buffered events, exclude the stream path.
app.add_middleware(GZipMiddleware, minimum_size=1000)

register_exception_handlers(app)

# Health SPECIFICALLY without the /api/v1 prefix — the router defines the full
# /api/health path (Render Health Check, devops.md section 1).
app.include_router(health.router)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(personas.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(account.router, prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")
app.include_router(results.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(exercises.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
