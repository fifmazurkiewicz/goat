"""Współdzielone singletony i fabryki DI — architecture.md §7: `Depends` FastAPI (i
analogiczne fabryki dla `BackgroundTasks`) żyją wyłącznie tutaj, domenowe serwisy same
nie znają FastAPI.

Singletony tutaj (`ModelPricingCache`, `ModerationService`) są bezstanowe względem
połączeń DB (nie trzymają otwartego `AsyncConnection` między wywołaniami) — bezpieczne
do współdzielenia między requestami/taskami w tym samym procesie.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.db import service_role_connection
from app.domain.moderation.service import ModerationService
from app.domain.usage.pricing import ModelPricingCache
from app.llm.openrouter_client import get_openrouter_client
from app.repositories.moderation_repo import ModerationEventsRepo


class ServiceRoleModerationEventsLogger:
    """Loguje `moderation_events` przez świeże, krótkotrwałe połączenie `service_role`
    (RLS blokuje INSERT/SELECT dla roli `authenticated` na tej tabeli, patrz
    `app/repositories/moderation_repo.py`) — bezpieczny singleton, nie trzyma połączenia
    otwartego między wywołaniami `.log(...)`."""

    async def log(self, **kwargs: object) -> None:
        async with service_role_connection() as conn:
            await ModerationEventsRepo(conn).log(**kwargs)  # type: ignore[arg-type]


@lru_cache
def get_pricing_cache() -> ModelPricingCache:
    return ModelPricingCache(
        get_openrouter_client(),
        refresh_seconds=settings.model_pricing_refresh_seconds,
        fallback_usd_per_token=settings.model_pricing_fallback_usd_per_token,
    )


@lru_cache
def get_moderation_service() -> ModerationService:
    return ModerationService(
        get_openrouter_client(),
        ServiceRoleModerationEventsLogger(),
        classifier_model=settings.openrouter_chat_model,
        random_sample_rate=settings.moderation_random_sample_rate,
    )
