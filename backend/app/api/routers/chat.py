"""Router `/chat` — SSE + multi-turn tool calling.

Wzorzec producer/consumer przez `asyncio.Queue` (`sse-starlette` `EventSourceResponse`,
`ping=15`) DOKŁADNIE wg docs/technical/architecture.md sekcja 3. Orkiestracja właściwa
żyje w `app/domain/chat/orchestrator.py` (`run_chat_turn`/`ChatOrchestrator`) — ten router
zostaje CIENKI (parsing requestu, cykl życia SSE, cancellation), zero logiki biznesowej.
"""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.db import rls_connection
from app.core.exceptions import NotFoundError
from app.core.security import AuthContext, get_current_user
from app.domain.chat.orchestrator import run_chat_turn
from app.models.schemas import ChatMessageOut, ChatSendMessage, ChatSessionCreate, ChatSessionOut
from app.repositories.chat_repo import ChatRepo
from app.repositories.personas_repo import PersonasRepo

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_chat_sessions(auth: AuthContext = Depends(get_current_user)) -> list[ChatSessionOut]:
    async with rls_connection(auth.claims) as conn:
        rows = await ChatRepo(conn).list_sessions()
    return [ChatSessionOut.model_validate(row) for row in rows]


@router.post("/sessions", response_model=ChatSessionOut, status_code=201)
async def create_chat_session(
    payload: ChatSessionCreate, auth: AuthContext = Depends(get_current_user)
) -> ChatSessionOut:
    """`persona_id=None` -> sesja `general` (auto-routing, ADR-13); podane -> sesja
    `persona` (1:1). Waliduje, że persona istnieje i jest widoczna dla usera PRZED
    utworzeniem sesji — inaczej FK `chat_sessions.persona_id` rzuciłby surowy błąd SQL."""
    async with rls_connection(auth.claims) as conn:
        if payload.persona_id is not None:
            persona = await PersonasRepo(conn).get_visible(payload.persona_id)
            if persona is None:
                raise NotFoundError(f"Persona {payload.persona_id!r} nie istnieje.")
            session_type = "persona"
        else:
            session_type = "general"

        row = await ChatRepo(conn).create_session(
            user_id=auth.user_id,
            persona_id=payload.persona_id,
            session_type=session_type,
            title=payload.title,
        )
    return ChatSessionOut.model_validate(row)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def list_chat_messages(
    session_id: str, auth: AuthContext = Depends(get_current_user)
) -> list[ChatMessageOut]:
    async with rls_connection(auth.claims) as conn:
        chat_repo = ChatRepo(conn)
        session = await chat_repo.get_session(session_id)
        if session is None or session.user_id != auth.user_id:
            raise NotFoundError(f"Sesja czatu {session_id!r} nie istnieje.")
        rows = await chat_repo.list_messages(session_id)
    return [ChatMessageOut.model_validate(row) for row in rows]


@router.post("/sessions/{session_id}/message")
async def send_chat_message(
    session_id: str,
    payload: ChatSendMessage,
    request: Request,
    auth: AuthContext = Depends(get_current_user),
) -> EventSourceResponse:
    """SSE — wzorzec producer/consumer z architecture.md §3. Połączenie DB NIE jest
    trzymane przez cały czas streamu (`run_chat_turn`/`ChatOrchestrator` otwierają
    krótkie, per-rundowe transakcje) — ten endpoint nie bierze `Depends` na DB."""
    queue: asyncio.Queue[dict] = asyncio.Queue()
    orchestrator_task = asyncio.create_task(
        run_chat_turn(
            user_id=auth.user_id,
            claims=auth.claims,
            session_id=session_id,
            user_message=payload.content,
            queue=queue,
        )
    )

    async def event_generator():
        try:
            loop = asyncio.get_event_loop()
            deadline = loop.time() + settings.chat_hard_timeout_s
            while True:
                if await request.is_disconnected():
                    orchestrator_task.cancel()
                    break
                remaining = deadline - loop.time()
                if remaining <= 0:
                    orchestrator_task.cancel()
                    yield {"event": "error", "data": '{"code":"timeout","message":"Przekroczono limit czasu odpowiedzi."}'}
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=min(15, remaining))
                except asyncio.TimeoutError:
                    continue  # sse-starlette samo wyśle ping (heartbeat)
                yield event
                if event["event"] in ("done", "error"):
                    break
        finally:
            if not orchestrator_task.done():
                orchestrator_task.cancel()

    return EventSourceResponse(event_generator(), ping=15)
