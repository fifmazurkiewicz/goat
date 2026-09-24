from __future__ import annotations

import asyncio

import pytest

from app.domain.usage import pricing
from app.domain.usage.pricing import ModelPricingCache


class _BlockedModelsProvider:
    def __init__(self, models: list[dict] | None = None) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self._models = models or []

    async def get_models(self) -> list[dict]:
        self.started.set()
        await self.release.wait()
        return self._models


@pytest.mark.asyncio
async def test_cold_pricing_refresh_does_not_block_chat_cost_estimate() -> None:
    provider = _BlockedModelsProvider()
    cache = ModelPricingCache(provider, fallback_usd_per_token=0.25)

    price = await asyncio.wait_for(cache.get_price_per_token("model"), timeout=0.1)

    assert price == (0.25, 0.25)
    await asyncio.wait_for(provider.started.wait(), timeout=0.1)
    provider.release.set()
    if cache._refresh_task is not None:
        await cache._refresh_task


@pytest.mark.asyncio
async def test_cold_refresh_does_not_warn_that_a_model_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _BlockedModelsProvider(
        [{"id": "google/gemini-3.7-flash", "pricing": {"prompt": "0.000001", "completion": "0.000002"}}]
    )
    cache = ModelPricingCache(provider, fallback_usd_per_token=0.25)
    warnings: list[tuple[str, dict]] = []
    monkeypatch.setattr(pricing.logger, "warning", lambda event, **kwargs: warnings.append((event, kwargs)))

    price = await cache.get_price_per_token("google/gemini-3.7-flash")

    assert price == (0.25, 0.25)
    assert warnings == []
    provider.release.set()
    if cache._refresh_task is not None:
        await cache._refresh_task
    assert await cache.get_price_per_token("google/gemini-3.7-flash") == (0.000001, 0.000002)
