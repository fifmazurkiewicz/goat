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

from app.api.routers import admin, chat, health, personas, plans, profile, results
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIDMiddleware, configure_logging

configure_logging(settings.environment)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("starting_up", environment=settings.environment)
    # TODO: reaper zawieszonych `plan_generation_jobs` (status="running" starszych niż
    # 5 min -> "error") uruchamiany tutaj przy starcie procesu. Chroni przed jobami
    # zawieszonymi po restarcie Render (brak persistent workera). Patrz
    # docs/technical/architecture.md sekcja 4 ("Background job — bez osobnego workera
    # na Render") i docs/adr/decisions.md ADR-1. Do zaimplementowania w etapie plan
    # generation (wymaga PlanGenerationJobsRepo, jeszcze nieistniejącego).
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
app.include_router(chat.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(results.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
