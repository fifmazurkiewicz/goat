"""Transport HTTP do OpenRoutera — `httpx.AsyncClient`, patrz docs/technical/ai-pipeline.md.

Modele domyślne konfigurowane przez env (`OPENROUTER_CHAT_MODEL`/`OPENROUTER_PLANNER_MODEL`,
`app/core/config.py`), NIGDY hardkodowane w tym module.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.llm.streaming import parse_sse_chunk

logger = structlog.get_logger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterClient:
    """Cienki wrapper `httpx.AsyncClient` nad OpenRouterem (chat completions + streaming).

    `tenacity` retry+backoff stosowany WYŁĄCZNIE przed pierwszym bajtem odpowiedzi
    streamu (ai-pipeline.md sekcja 7) — streamu nie da się bezpiecznie powtórzyć po
    wysłaniu części tokenów do klienta SSE. Dla wywołań non-streaming (`complete_json`,
    `get_models`) retry obejmuje całe wywołanie — bezpieczne, bo nic nie wyciekło jeszcze
    do klienta końcowego.
    """

    def __init__(self, api_key: str | None = None, base_url: str = OPENROUTER_BASE_URL) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": (
                    f"Bearer {api_key or settings.openrouter_api_key.get_secret_value()}"
                ),
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
        """Streamuje chat completion z OpenRoutera, yielduje sparsowane chunki SSE
        (`{"choices": [{"delta": {...}, "finish_reason": ...}], "usage": {...}}`).

        `usage: {"include": true}` w body — wymagane, żeby finalny chunk streamu
        zawierał `prompt_tokens`/`completion_tokens` (ai-pipeline.md §1b, koszt USD).

        Retry (max 3 próby, exponential backoff) obejmuje WYŁĄCZNIE fazę przed pierwszym
        wyemitowanym chunkiem — po pierwszym `yield` błąd propaguje się wprost (nie da
        się bezpiecznie powtórzyć streamu po wysłaniu części tokenów do klienta SSE).
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
            payload["models"] = [model, *fallback_models]

        last_exc: Exception | None = None
        for attempt in range(3):
            yielded_any = False
            try:
                async with self._client.stream(
                    "POST", "/chat/completions", json=payload
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ExternalServiceError(
                            f"OpenRouter zwrócił błąd {response.status_code}: {body[:500]!r}"
                        )
                    async for line in response.aiter_lines():
                        chunk = parse_sse_chunk(line)
                        if chunk is None:
                            continue
                        yielded_any = True
                        yield chunk
                return
            except (httpx.HTTPError, ExternalServiceError) as exc:
                last_exc = exc
                if yielded_any:
                    # Część tokenów już poszła do klienta SSE — nie da się bezpiecznie
                    # powtórzyć, propagujemy błąd wprost (ai-pipeline.md §7).
                    raise
                logger.warning(
                    "openrouter_stream_retry", attempt=attempt + 1, error=str(exc)
                )
                continue

        raise ExternalServiceError(
            f"OpenRouter niedostępny po 3 próbach: {last_exc}"
        ) from last_exc

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8))
    async def complete_json(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        json_schema: dict[str, Any],
        max_tokens: int = 300,
    ) -> dict[str, Any]:
        """Wywołanie non-streaming z `response_format: json_schema` (strict) — używane
        przez `ModerationService` i `ChatRoutingService` (ai-pipeline.md §1a, §5).

        `provider.require_parameters: true` — nie routuj do endpointu bez wsparcia
        `json_schema` (ai-pipeline.md §1).
        """
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_schema", "json_schema": json_schema},
            "provider": {"require_parameters": True},
        }
        response = await self._client.post("/chat/completions", json=payload)
        if response.status_code >= 400:
            raise ExternalServiceError(
                f"OpenRouter zwrócił błąd {response.status_code}: {response.text[:500]!r}"
            )
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        result: dict[str, Any] = json.loads(content)
        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8))
    async def get_models(self) -> list[dict[str, Any]]:
        """`GET /api/v1/models` — cennik modeli (ai-pipeline.md §1b), cache'owany przez
        `app/domain/usage/pricing.py`, NIE tutaj (transport nie zna polityki cache)."""
        response = await self._client.get("/models")
        if response.status_code >= 400:
            raise ExternalServiceError(
                f"OpenRouter /models zwrócił błąd {response.status_code}"
            )
        data: list[dict[str, Any]] = response.json()["data"]
        return data

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_openrouter_client() -> OpenRouterClient:
    """Singleton per proces — `httpx.AsyncClient` ma własny connection pool i nie
    powinien być tworzony per-request (wyciek połączeń/gniazd)."""
    return OpenRouterClient()
