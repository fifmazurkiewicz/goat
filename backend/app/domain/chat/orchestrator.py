"""`ChatOrchestrator` — pętla SSE + multi-turn tool calling.

Pełna implementacja: docs/technical/architecture.md sekcja 3 ("Chat — SSE + multi-turn
tool calling"). Ten plik jest świadomym szkieletem fazy fundamentu — logika biznesowa
(wywołanie OpenRoutera, akumulacja `tool_calls`, walidacja+zapis `log_result`, zapis
`assistant`+`tool` message w jednej transakcji, pętla max 3-5 rund, cancellation) to
osobny, kolejny etap.

Zależności jako `Protocol` (nie konkretne klasy) — zgodnie z architecture.md sekcja 7:
domenowe serwisy nie znają FastAPI/HTTP i są testowalne bez bazy przez podstawienie fejków.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol


class LLMClientProtocol(Protocol):
    async def stream_chat(
        self, *, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any: ...


class ChatRepositoryProtocol(Protocol):
    async def save_turn(self, *args: Any, **kwargs: Any) -> Any: ...


class ChatOrchestrator:
    """Producer strony agregatora SSE — wypełnia `asyncio.Queue` konsumowaną przez
    endpoint `/chat` (`sse-starlette` `EventSourceResponse`, patrz api/routers/chat.py)."""

    def __init__(self, llm_client: LLMClientProtocol, chat_repo: ChatRepositoryProtocol) -> None:
        self._llm_client = llm_client
        self._chat_repo = chat_repo

    async def handle_message(
        self,
        *,
        session_id: str,
        user_message: str,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> None:
        """Obsługuje jedną wiadomość usera: streamuje tokeny + tool calling do `queue`.

        Kontrakt zdarzeń wysyłanych do `queue` (docs/technical/architecture.md sekcja 3):
        `token`, `tool_call_start`, `tool_result`, `done`, `error`.

        TODO pełna implementacja — patrz architecture.md sekcja 3:
        0. System prompt budowany przez `ContextBuilder`: platform preambuł + persona
           `system_prompt` + blok `user_profile` + (gdy niekompletny) instrukcja z
           `app/domain/chat/tools.py::build_profile_intake_instruction` (ai-pipeline.md §0).
        1. `httpx.AsyncClient.stream(...)` do OpenRoutera z
           `tools=[log_result_schema, UPDATE_USER_PROFILE_TOOL_SCHEMA]` (`app/domain/chat/tools.py`).
        2. `delta.content` -> `queue.put({"event": "token", ...})`.
        3. `delta.tool_calls` -> akumulacja w `dict[int, ToolCallBuffer]` (patrz
           `app/llm/tool_calling.py`) aż `finish_reason == "tool_calls"`.
        4. Walidacja Pydantic argumentów (niezaufany input) + zapis `results` (batch) lub
           `user_profile` (przez `UserProfileRepo.upsert`, patrz `app/models/schemas.py`
           `UserProfileUpdate`) w zależności od nazwy narzędzia.
        5. Zapis `assistant`+`tool` message w JEDNEJ transakcji (spójność historii).
        6. Kolejna runda do skutku (`finish_reason == "stop"`) lub twardy limit 3-5 rund.
        7. Krótkie transakcje per rundę — połączenie DB NIE żyje przez cały stream
           (wyczerpanie puli Supavisor przy kilku równoległych czatach).
        8. Nie łapać `asyncio.CancelledError` szerokim `except Exception`.
        """
        raise NotImplementedError(
            "ChatOrchestrator.handle_message — do zaimplementowania w etapie chat "
            "orchestratora, patrz docs/technical/architecture.md sekcja 3."
        )
