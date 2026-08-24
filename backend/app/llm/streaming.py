"""Parser for raw OpenRouter SSE chunks -> domain events.

Input format (SSE, OpenAI-compatible): each block is a `data: <json>` line followed by
a blank line; the stream ends with sentinel `data: [DONE]`, e.g.:

    data: {"id":"...","choices":[{"delta":{"content":"Hello"}}]}

    data: {"id":"...","choices":[{"delta":{"tool_calls":[...]}}]}

    data: [DONE]

Full implementation: docs/technical/architecture.md section 3 — `delta.content` ->
`token` event, `delta.tool_calls` (fragments: `id`+`name` in the first chunk for a
given `index`, `arguments` appended piecewise) -> accumulation via `app/llm/tool_calling.py`.
"""

from __future__ import annotations

import json
from typing import Any


def parse_sse_chunk(raw: str) -> dict[str, Any] | None:
    """Parse a single line from the raw OpenRouter SSE stream.

    Returns parsed JSON for the chunk, or `None` for the `[DONE]` sentinel, an empty
    line (SSE block separator), or an SSE comment (line starting with `:`, used by some
    proxies as a heartbeat).

    Accepts both lines with a `data: ` prefix (typical `httpx.Response.aiter_lines()`
    output on raw SSE body) and content already stripped of the prefix — resilience to
    minor differences in where exactly the line comes from in the pipeline.
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
