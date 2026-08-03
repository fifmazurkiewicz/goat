"""Cennik modeli OpenRouter — cache in-memory, odświeżany okresowo (ai-pipeline.md §1b).

Ceny modeli na OpenRouterze zmieniają się w czasie, więc NIE są hardkodowane — pobierane
z `GET /api/v1/models` (`pricing.prompt`/`pricing.completion`, USD za token) i trzymane
w pamięci procesu z TTL. Odświeżanie leniwe (przy pierwszym użyciu po wygaśnięciu TTL),
nie osobny scheduler/thread — prostsze i wystarczające dla skali tej aplikacji.
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
    """Nie zna FastAPI/HTTP — testowalna z fake `ModelsProviderProtocol`."""

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
            except Exception as exc:  # noqa: BLE001 — transport/parsing awarii nie eskalujemy
                logger.warning("model_pricing_refresh_failed", error=str(exc))
                return  # zachowujemy ostatnią znaną wartość z cache (ai-pipeline.md §1b)

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
        """`(prompt_usd_per_token, completion_usd_per_token)`. Fallback konserwatywny
        (górna granica) gdy model nieznany w cache albo cache pusty (zimny start) —
        celowo NIE wpuszcza darmowego użycia przy braku danych o cenie."""
        await self.refresh()
        if model in self._prices:
            return self._prices[model]
        logger.warning("model_pricing_unknown_model", model=model)
        return (self._fallback, self._fallback)

    async def estimate_cost_usd(
        self, *, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        prompt_price, completion_price = await self.get_price_per_token(model)
        return prompt_tokens * prompt_price + completion_tokens * completion_price
