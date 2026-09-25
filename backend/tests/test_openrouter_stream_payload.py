from __future__ import annotations

import json

import httpx
import pytest

from app.llm.openrouter_client import OpenRouterClient


@pytest.mark.asyncio
async def test_stream_payload_uses_ordered_models_contract_and_prioritizes_throughput() -> None:
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
                fallback_models=["primary/model", "fallback/model"],
            )
        ]
    finally:
        await client.aclose()

    assert chunks
    assert "model" not in captured
    assert captured["models"] == ["primary/model", "fallback/model"]
    assert captured["provider"] == {"sort": "throughput"}


@pytest.mark.asyncio
async def test_stream_retries_a_fallback_after_an_empty_successful_stream() -> None:
    requests: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(
                200,
                content=b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
            )
        return httpx.Response(
            200,
            content=b'data: {"choices":[{"delta":{"content":"fallback"},"finish_reason":"stop"}]}\n\n',
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

    assert chunks[-1]["choices"][0]["delta"]["content"] == "fallback"
    assert requests[0]["models"] == ["primary/model", "fallback/model"]
    assert requests[1]["model"] == "fallback/model"
    assert "models" not in requests[1]
