"""Router `/chat` — SSE + multi-turn tool calling.

Pełny wzorzec endpointu streamującego (producer/consumer przez `asyncio.Queue`,
`EventSourceResponse` z `ping=15`) opisany w docs/technical/architecture.md sekcja 3.
Ten plik to celowo cienki szkielet — orkiestracja żyje w
`app/domain/chat/orchestrator.py::ChatOrchestrator`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import AuthContext, get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions")
async def list_chat_sessions(auth: AuthContext = Depends(get_current_user)) -> list[dict]:
    # TODO: pełna implementacja — patrz docs/technical/architecture.md.
    return []


# TODO: `POST /chat/sessions/{session_id}/messages` -> EventSourceResponse, patrz
# architecture.md sekcja 3 dla pełnego wzorca (asyncio.Queue, heartbeat, cancellation
# przez request.is_disconnected(), delegacja do ChatOrchestrator.handle_message).
