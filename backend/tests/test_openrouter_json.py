"""Structured-response failures remain actionable after transport retries."""

from unittest.mock import Mock

import httpx
import pytest
from tenacity import wait_none

from app.core.exceptions import ExternalServiceError
from app.llm import openrouter_client as module


@pytest.mark.parametrize(
    ("content", "finish_reason", "expected"),
    [
        ('{"private-user-note":', "stop", "nieprawidłowy format"),
        ('{"items": []}', "length", "ucięta"),
        (None, "stop", "nie zwrócił treści"),
        ("   ", "stop", "nie zwrócił treści"),
        ("", "content_filter", "zablokował"),
        ("[]", "stop", "strukturę"),
    ],
)
async def test_json_failures_retry_without_exposing_content(monkeypatch, content, finish_reason, expected):
    calls = 0
    logger = Mock()
    monkeypatch.setattr(module, "logger", logger)

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
                "usage": {"completion_tokens": 123},
            },
        )

    client = module.OpenRouterClient(api_key="test")
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url="https://example.test", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ExternalServiceError, match=expected) as error:
            await module.OpenRouterClient.complete_json.retry_with(wait=wait_none())(
                client,
                model="test/model",
                messages=[],
                json_schema={},
            )
    finally:
        await client.aclose()
    assert calls == 3
    assert "RetryError" not in str(error.value)
    assert "private-user-note" not in str(error.value)
    assert "private-user-note" not in str(logger.warning.call_args_list)
    assert logger.warning.call_args.kwargs["finish_reason"] == finish_reason
    assert logger.warning.call_args.kwargs["completion_tokens"] == 123
    logger.info.assert_not_called()


async def test_json_success_after_invalid_response(monkeypatch):
    calls = 0
    logger = Mock()
    monkeypatch.setattr(module, "logger", logger)

    async def handler(request):
        nonlocal calls
        calls += 1
        content = "invalid" if calls == 1 else '{"items": []}'
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})

    client = module.OpenRouterClient(api_key="test")
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url="https://example.test", transport=httpx.MockTransport(handler))
    try:
        result = await module.OpenRouterClient.complete_json.retry_with(wait=wait_none())(
            client,
            model="test/model",
            messages=[],
            json_schema={},
        )
    finally:
        await client.aclose()
    assert result == {"items": []}
    assert calls == 2
    logger.warning.assert_called_once()
    logger.info.assert_called_once()
