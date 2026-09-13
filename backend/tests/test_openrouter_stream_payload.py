from __future__ import annotations

import json

import httpx
import pytest

from app.llm.openrouter_client import OpenRouterClient


@pytest.mark.asyncio
async def test_stream_payload_prioritizes_throughput_and_does_not_duplicate_primary() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            content=b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\n',
        )

    client = OpenRouterClient(api_key="test", base_url="https://example.test")
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
    )
    try:
        chunks = [
            chunk
            async for chunk in client.stream_chat(
                model="primary/model",
                messages=[{"role": "user", "content": "hi"}],
                fallback_models=["fallback/model"],
            )
        ]
    finally:
        await client.aclose()

    assert chunks
    assert captured["model"] == "primary/model"
    assert captured["models"] == ["fallback/model"]
    assert captured["provider"] == {"sort": "throughput"}
