from __future__ import annotations

import asyncio

import pytest

from app.domain.usage.pricing import ModelPricingCache


class _BlockedModelsProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def get_models(self) -> list[dict]:
        self.started.set()
        await self.release.wait()
        return []


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
