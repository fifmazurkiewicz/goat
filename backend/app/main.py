"""Punkt wejścia aplikacji FastAPI — Multi-Persona Coaching App backend.

Struktura zgodna z docs/technical/architecture.md sekcja 1: routery pod `/api/v1`
(health poza tym prefiksem, patrz devops.md — Render Health Check = `/api/health`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    account,
    admin,
    chat,
    exercises,
    health,
    personas,
    plans,
    profile,
    results,
    templates,
)
from app.core.config import settings
from app.core.db import service_role_connection
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIDMiddleware, configure_logging
from app.domain.results.metrics_cache import allowed_metrics_cache
from app.repositories.allowed_metrics_repo import AllowedMetricsRepo
from app.repositories.plans_repo import PlansRepo

configure_logging(settings.environment)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("starting_up", environment=settings.environment)

    # Reaper zawieszonych `plan_generation_jobs` (ADR-1, architecture.md §4) — chroni
    # przed jobami zawieszonymi w statusie 'pending'/'running' po restarcie Render (brak
    # persistent workera, więc nic inaczej by ich nie odblokowało). `service_role`, bo
    # operuje na WSZYSTKICH userach, nie jednym w kontekście RLS.
    async with service_role_connection() as conn:
        reaped = await PlansRepo(conn).reap_stale_jobs(
            older_than_minutes=settings.plan_reaper_stale_minutes
        )
        if reaped:
            logger.warning("plan_jobs_reaped", job_ids=reaped, count=len(reaped))

        # `allowed_metrics` — cache in-memory, hot-path przy `log_result` w trakcie
        # streamu SSE (nie chcemy zapytania SQL per tool call).
        await allowed_metrics_cache.load(AllowedMetricsRepo(conn))

    yield
    logger.info("shutting_down")


app = FastAPI(
    title="Multi-Persona Coaching App API",
    version="0.1.0",
    lifespan=lifespan,
)

# Allowlist jawny (docs/technical/security.md sekcja 5) + regex dla Vercel preview
# deployments — NIGDY wildcard "*", zwłaszcza przy nagłówku Authorization.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)

register_exception_handlers(app)

# Health SPECJALNIE bez prefiksu /api/v1 — router definiuje pełną ścieżkę /api/health
# (Render Health Check, devops.md sekcja 1).
app.include_router(health.router)

app.include_router(personas.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(account.router, prefix="/api/v1")
app.include_router(results.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(exercises.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
