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
from app.domain.moderation.service import ModerationService
from app.domain.usage.pricing import ModelPricingCache
from app.llm.openrouter_client import get_openrouter_client


class DisabledModerationEventsLogger:
    """Safety classification remains active; the retired admin event log does not."""

    async def log(self, **kwargs: object) -> None:
        return None


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
        DisabledModerationEventsLogger(),
        classifier_model=settings.openrouter_chat_model,
        random_sample_rate=settings.moderation_random_sample_rate,
    )
