"""Accumulation of `tool_calls` fragments streamed in pieces by OpenRouter.

The first chunk for a given tool call carries `id`+`function.name`; subsequent chunks
append `function.arguments` fragments (JSON string built incrementally) — see
docs/technical/architecture.md section 3, orchestrator loop step 3.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallBuffer:
    """Buffer for a single tool call, held in `dict[int, ToolCallBuffer]` keyed by
    OpenRouter delta `index` (not `id` — `id` may arrive only in the first chunk for
    that index), per architecture.md section 3."""

    id: str | None = None
    name: str | None = None
    arguments_buffer: io.StringIO = field(default_factory=io.StringIO)

    def accumulate(self, delta: dict[str, Any]) -> None:
        """Append the next tool_call delta fragment to the buffer."""
        tool_call_id = delta.get("id")
        if tool_call_id and self.id is None:
            self.id = tool_call_id

        function = delta.get("function") or {}
        name = function.get("name")
        if name and self.name is None:
            self.name = name

        arguments_fragment = function.get("arguments")
        if arguments_fragment:
            self.arguments_buffer.write(arguments_fragment)

    def get_arguments_json(self) -> str:
        """Full accumulated JSON arguments string — parse (`json.loads`) and validate
        with Pydantic only after `finish_reason == 'tool_calls'`, as untrusted input
        (security.md section 3)."""
        return self.arguments_buffer.getvalue()
