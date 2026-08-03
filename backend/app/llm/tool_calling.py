"""Akumulacja fragmentów `tool_calls` streamowanych kawałkami przez OpenRouter.

Pierwszy chunk dla danego tool call niesie `id`+`function.name`, kolejne chunki
dokładają fragmenty `function.arguments` (string JSON budowany przyrostowo) — patrz
docs/technical/architecture.md sekcja 3, pkt 3 pętli orkiestratora.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallBuffer:
    """Bufor pojedynczego tool call, trzymany w `dict[int, ToolCallBuffer]` keyed po
    `index` z delty OpenRoutera (nie po `id` — `id` może przyjść dopiero w pierwszym
    chunku danego indeksu), zgodnie z architecture.md sekcja 3."""

    id: str | None = None
    name: str | None = None
    arguments_buffer: io.StringIO = field(default_factory=io.StringIO)

    def accumulate(self, delta: dict[str, Any]) -> None:
        """Doklejenie kolejnego fragmentu tool_call delty do bufora."""
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
        """Pełny, zakumulowany string JSON argumentów — parsować (`json.loads`) i
        walidować przez Pydantic dopiero po `finish_reason == 'tool_calls'`, jako
        niezaufany input (security.md sekcja 3)."""
        return self.arguments_buffer.getvalue()
