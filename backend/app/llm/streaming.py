"""Parser surowych chunków SSE OpenRoutera -> zdarzenia domenowe.

Format wejściowy (SSE, kompatybilny z OpenAI): każdy blok to linia `data: <json>`
zakończona pustą linią, strumień kończy się sentinelem `data: [DONE]`, np.:

    data: {"id":"...","choices":[{"delta":{"content":"Cześć"}}]}

    data: {"id":"...","choices":[{"delta":{"tool_calls":[...]}}]}

    data: [DONE]

Pełna implementacja: docs/technical/architecture.md sekcja 3 — `delta.content` ->
zdarzenie `token`, `delta.tool_calls` (fragmenty: `id`+`name` w pierwszym chunku danego
`index`, `arguments` doklejane kawałkami) -> akumulacja przez `app/llm/tool_calling.py`.
"""

from __future__ import annotations

import json
from typing import Any


def parse_sse_chunk(raw: str) -> dict[str, Any] | None:
    """Parsuje pojedynczą linię surowego strumienia SSE OpenRoutera.

    Zwraca sparsowany JSON danego chunku, albo `None` dla sentinela `[DONE]`, pustej
    linii (separator bloków SSE) albo komentarza SSE (linia zaczynająca się od `:`,
    używana przez niektóre proxy jako heartbeat).

    Akceptuje zarówno linie z prefiksem `data: ` (typowy output `httpx.Response.aiter_lines()`
    na surowym body SSE), jak i już-odartą z prefiksu treść — odporność na drobne różnice
    w tym, skąd dokładnie linia pochodzi w pipeline'ie.
    """
    line = raw.strip()
    if not line or line.startswith(":"):
        return None

    payload = line[len("data:") :].strip() if line.startswith("data:") else line
    if payload == "[DONE]":
        return None
    if not payload:
        return None

    return json.loads(payload)  # type: ignore[no-any-return]
