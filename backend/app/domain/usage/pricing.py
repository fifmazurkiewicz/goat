"""OpenRouter model pricing — in-memory cache, refreshed periodically (ai-pipeline.md §1b).

Model prices on OpenRouter change over time, so they are NOT hardcoded — fetched from
`GET /api/v1/models` (`pricing.prompt`/`pricing.completion`, USD per token) and kept
in process memory with TTL. Lazy refresh (on first use after TTL expiry), not a separate
scheduler/thread — simpler and sufficient at this app's scale.
"""

from __future__ import annotations

import asyncio
import time
from typing import Protocol

import structlog

logger = structlog.get_logger(__name__)


class ModelsProviderProtocol(Protocol):
    async def get_models(self) -> list[dict]: ...


class ModelPricingCache:
    """Does not know FastAPI/HTTP — testable with a fake `ModelsProviderProtocol`."""

    def __init__(
        self,
        client: ModelsProviderProtocol,
        *,
        refresh_seconds: int = 3600,
        fallback_usd_per_token: float = 0.00003,
    ) -> None:
        self._client = client
        self._refresh_seconds = refresh_seconds
        self._fallback = fallback_usd_per_token
        self._prices: dict[str, tuple[float, float]] = {}
        self._last_refresh: float = 0.0
        self._lock = asyncio.Lock()

    async def refresh(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and self._prices and (now - self._last_refresh) < self._refresh_seconds:
            return
        async with self._lock:
            now = time.monotonic()
            if not force and self._prices and (now - self._last_refresh) < self._refresh_seconds:
                return
            try:
                models = await self._client.get_models()
            except Exception as exc:  # noqa: BLE001 — transport/parsing failures are not escalated
                logger.warning("model_pricing_refresh_failed", error=str(exc))
                return  # keep last known cache value (ai-pipeline.md §1b)

            prices: dict[str, tuple[float, float]] = {}
            for model in models:
                pricing = model.get("pricing") or {}
                try:
                    prompt_price = float(pricing.get("prompt") or 0)
                    completion_price = float(pricing.get("completion") or 0)
                except (TypeError, ValueError):
                    continue
                model_id = model.get("id")
                if model_id:
                    prices[model_id] = (prompt_price, completion_price)

            if prices:
                self._prices = prices
                self._last_refresh = now

    async def get_price_per_token(self, model: str) -> tuple[float, float]:
        """`(prompt_usd_per_token, completion_usd_per_token)`. Conservative fallback
        (upper bound) when the model is unknown in cache or cache is empty (cold start) —
        deliberately does NOT allow free usage when price data is missing."""
        await self.refresh()
        if model in self._prices:
            return self._prices[model]
        logger.warning("model_pricing_unknown_model", model=model)
        return (self._fallback, self._fallback)

    async def estimate_cost_usd(self, *, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        prompt_price, completion_price = await self.get_price_per_token(model)
        return prompt_tokens * prompt_price + completion_tokens * completion_price
