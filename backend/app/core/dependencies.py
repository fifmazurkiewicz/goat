"""Shared singletons and DI factories — architecture.md §7: FastAPI `Depends` (and
analogous factories for `BackgroundTasks`) live only here; domain services don't
know FastAPI themselves.

The singletons here (`ModelPricingCache`, `ModerationService`) are stateless w.r.t.
DB connections (don't hold an open `AsyncConnection` between calls) — safe to share
between requests/tasks in the same process.
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
    """Logs `moderation_events` via a fresh, short-lived `service_role` connection
    (RLS blocks INSERT/SELECT for the `authenticated` role on this table, see
    `app/repositories/moderation_repo.py`) — a safe singleton, doesn't hold the
    connection open between `.log(...)` calls."""

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
