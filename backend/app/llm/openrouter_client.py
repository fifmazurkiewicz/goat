"""HTTP transport to OpenRouter — `httpx.AsyncClient`, see docs/technical/ai-pipeline.md.

Default models configured via env (`OPENROUTER_CHAT_MODEL`/`OPENROUTER_PLANNER_MODEL`,
`app/core/config.py`), NEVER hardcoded in this module.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.llm.streaming import parse_sse_chunk
from app.observability.langfuse import observe
from app.observability.langfuse import update as update_observation

logger = structlog.get_logger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterClient:
    """Thin `httpx.AsyncClient` wrapper over OpenRouter (chat completions + streaming).

    `tenacity` retry+backoff applies ONLY before the first byte of a stream response
    (ai-pipeline.md section 7) — a stream cannot be safely retried after partial tokens
    were sent to the SSE client. For non-streaming calls (`complete_json`, `get_models`)
    retry covers the whole call — safe because nothing has leaked to the end client yet.
    """

    def __init__(self, api_key: str | None = None, base_url: str = OPENROUTER_BASE_URL) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": (f"Bearer {api_key or settings.openrouter_api_key.get_secret_value()}"),
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def stream_chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        fallback_models: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat completion from OpenRouter, yielding parsed SSE chunks
        (`{"choices": [{"delta": {...}, "finish_reason": ...}], "usage": {...}}`).

        `usage: {"include": true}` in the body — required so the final stream chunk
        includes `prompt_tokens`/`completion_tokens` (ai-pipeline.md §1b, USD cost).

        Retry (max 3 attempts, exponential backoff) covers ONLY the phase before the
        first emitted chunk — after the first `yield` errors propagate directly (the
        stream cannot be safely retried after partial tokens were sent to the SSE client).
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "usage": {"include": True},
        }
        if tools:
            payload["tools"] = tools
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if fallback_models:
            # OpenRouter's multi-model contract uses one ordered `models` list;
            # its first entry is the primary model and the remaining entries are
            # fallbacks. Do not send the mutually ambiguous `model` + `models`
            # combination.
            payload.pop("model")
            payload["models"] = list(dict.fromkeys([model, *fallback_models]))
        if settings.openrouter_provider_sort:
            payload["provider"] = {"sort": settings.openrouter_provider_sort}

        completion: list[str] = []
        usage: dict[str, Any] = {}
        with observe(
            name="openrouter.stream_chat",
            as_type="generation",
            input=messages,
            metadata={"tools": tools, "max_tokens": max_tokens, "fallback_models": fallback_models},
            model=model,
        ) as observation:
            retry_payloads = [payload]
            for fallback_model in dict.fromkeys(fallback_models or []):
                retry_payload = {**payload, "model": fallback_model}
                retry_payload.pop("models", None)
                retry_payloads.append(retry_payload)

            for request_payload in retry_payloads:
                last_exc: Exception | None = None
                for attempt in range(3):
                    yielded_any = False
                    yielded_meaningful = False
                    try:
                        async with self._client.stream("POST", "/chat/completions", json=request_payload) as response:
                            if response.status_code >= 400:
                                body = await response.aread()
                                raise ExternalServiceError(
                                    f"OpenRouter zwrócił błąd {response.status_code}: {body[:500]!r}"
                                )
                            async for line in response.aiter_lines():
                                chunk = parse_sse_chunk(line)
                                if chunk is None:
                                    continue
                                usage = chunk.get("usage") or usage
                                for choice in chunk.get("choices") or []:
                                    delta = choice.get("delta") or {}
                                    completion.append(delta.get("content") or "")
                                    yielded_meaningful |= bool(delta.get("content") or delta.get("tool_calls"))
                                yielded_any = True
                                yield chunk
                        if yielded_meaningful:
                            update_observation(observation, output="".join(completion), usage_details=usage or None)
                            return
                        logger.warning("openrouter_empty_stream_retry", model=request_payload.get("model", model))
                        break
                    except (httpx.HTTPError, ExternalServiceError) as exc:
                        last_exc = exc
                        if yielded_any:
                            # Some tokens already went to the SSE client — cannot safely
                            # retry; propagate the error directly (ai-pipeline.md §7).
                            raise
                        logger.warning("openrouter_stream_retry", attempt=attempt + 1, error=str(exc))
                else:
                    raise ExternalServiceError(f"OpenRouter niedostępny po 3 próbach: {last_exc}") from last_exc

            update_observation(observation, output="", usage_details=usage or None)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8))
    async def complete_json(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        json_schema: dict[str, Any],
        max_tokens: int = 300,
    ) -> dict[str, Any]:
        """Non-streaming call with `response_format: json_schema` (strict) — used by
        `ModerationService` and `ChatRoutingService` (ai-pipeline.md §1a, §5).

        `provider.require_parameters: true` — do not route to an endpoint without
        `json_schema` support (ai-pipeline.md §1).
        """
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_schema", "json_schema": json_schema},
            "provider": {"require_parameters": True},
        }
        started_at = time.perf_counter()
        with observe(
            name="openrouter.complete_json",
            as_type="generation",
            input=messages,
            metadata={"json_schema": json_schema, "max_tokens": max_tokens},
            model=model,
        ) as observation:
            response = await self._client.post("/chat/completions", json=payload)
            if response.status_code >= 400:
                raise ExternalServiceError(f"OpenRouter zwrócił błąd {response.status_code}: {response.text[:500]!r}")
            data = response.json()
        usage = data.get("usage") or {}
        logger.info(
            "openrouter_json_completed",
            model=model,
            duration_ms=round((time.perf_counter() - started_at) * 1000),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
        content = data["choices"][0]["message"]["content"]
        update_observation(observation, output=content, usage_details=usage or None)
        result: dict[str, Any] = json.loads(content)
        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8))
    async def get_models(self) -> list[dict[str, Any]]:
        """`GET /api/v1/models` — model pricing (ai-pipeline.md §1b), cached by
        `app/domain/usage/pricing.py`, NOT here (transport layer has no cache policy)."""
        response = await self._client.get("/models")
        if response.status_code >= 400:
            raise ExternalServiceError(f"OpenRouter /models zwrócił błąd {response.status_code}")
        data: list[dict[str, Any]] = response.json()["data"]
        return data

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_openrouter_client() -> OpenRouterClient:
    """Singleton per process — `httpx.AsyncClient` has its own connection pool and should
    not be created per request (socket/connection leak)."""
    return OpenRouterClient()
