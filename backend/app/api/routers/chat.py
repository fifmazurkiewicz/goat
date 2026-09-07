"""`/chat` router — SSE + multi-turn tool calling.

Producer/consumer pattern via `asyncio.Queue` (`sse-starlette` `EventSourceResponse`,
`ping=15`) EXACTLY per docs/technical/architecture.md section 3. The actual
orchestration lives in `app/domain/chat/orchestrator.py`
(`run_chat_turn`/`ChatOrchestrator`) — this router stays THIN (request parsing, SSE
lifecycle, cancellation), zero business logic.
"""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.db import rls_connection
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import AuthContext, get_current_user, require_approved
from app.domain.chat.orchestrator import run_chat_turn
from app.domain.chat.turn_registry import (
    cancel_turn,
    is_turn_in_progress,
    mark_turn_finished,
    mark_turn_started,
    should_conflict_chat_send,
)
from app.models.schemas import (
    ChatMessageOut,
    ChatSendMessage,
    ChatSessionCreate,
    ChatSessionOut,
    ChatSessionTurnStatus,
    ChatSessionUpdate,
)
from app.repositories.chat_repo import ChatRepo
from app.repositories.personas_repo import PersonasRepo

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_approved)])


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_chat_sessions(auth: AuthContext = Depends(get_current_user)) -> list[ChatSessionOut]:
    async with rls_connection(auth.claims) as conn:
        rows = await ChatRepo(conn).list_sessions()
    return [ChatSessionOut.model_validate(row) for row in rows]


@router.post("/sessions", response_model=ChatSessionOut, status_code=201)
async def create_chat_session(
    payload: ChatSessionCreate, auth: AuthContext = Depends(get_current_user)
) -> ChatSessionOut:
    """`persona_id=None` -> `general` session (auto-routing, ADR-13); given -> `persona`
    session (1:1). Validates that the persona exists and is visible to the user BEFORE
    creating the session — otherwise the `chat_sessions.persona_id` FK would throw a raw
    SQL error."""
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


@router.patch("/sessions/{session_id}", response_model=ChatSessionOut)
async def update_chat_session(
    session_id: str,
    payload: ChatSessionUpdate,
    auth: AuthContext = Depends(get_current_user),
) -> ChatSessionOut:
    async with rls_connection(auth.claims) as conn:
        chat_repo = ChatRepo(conn)
        session = await chat_repo.get_session(session_id)
        if session is None or session.user_id != auth.user_id:
            raise NotFoundError(f"Sesja czatu {session_id!r} nie istnieje.")
        row = await chat_repo.update_session_title(session_id, payload.title.strip())
    if row is None:
        raise NotFoundError(f"Sesja czatu {session_id!r} nie istnieje.")
    return ChatSessionOut.model_validate(row)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_chat_session(
    session_id: str, auth: AuthContext = Depends(get_current_user)
) -> None:
    async with rls_connection(auth.claims) as conn:
        chat_repo = ChatRepo(conn)
        session = await chat_repo.get_session(session_id)
        if session is None or session.user_id != auth.user_id:
            raise NotFoundError(f"Sesja czatu {session_id!r} nie istnieje.")
        await chat_repo.delete_session(session_id)


@router.get("/sessions/{session_id}/turn-status", response_model=ChatSessionTurnStatus)
async def chat_turn_status(
    session_id: str, auth: AuthContext = Depends(get_current_user)
) -> ChatSessionTurnStatus:
    async with rls_connection(auth.claims) as conn:
        session = await ChatRepo(conn).get_session(session_id)
        if session is None or session.user_id != auth.user_id:
            raise NotFoundError(f"Sesja czatu {session_id!r} nie istnieje.")
        in_progress = session.turn_in_progress or is_turn_in_progress(session_id)
    return ChatSessionTurnStatus(in_progress=in_progress)


@router.post("/sessions/{session_id}/cancel", status_code=204)
async def cancel_chat_turn(
    session_id: str, auth: AuthContext = Depends(get_current_user)
) -> None:
    """Stop generation — user clicked Stop (unlike navigating away from the chat,
    where the turn may continue in the background)."""
    async with rls_connection(auth.claims) as conn:
        session = await ChatRepo(conn).get_session(session_id)
        if session is None or session.user_id != auth.user_id:
            raise NotFoundError(f"Sesja czatu {session_id!r} nie istnieje.")
    cancel_turn(session_id)


@router.post("/sessions/{session_id}/message")
async def send_chat_message(
    session_id: str,
    payload: ChatSendMessage,
    request: Request,
    auth: AuthContext = Depends(get_current_user),
) -> EventSourceResponse:
    """SSE — producer/consumer pattern from architecture.md §3. The DB connection is
    NOT held for the entire stream duration (`run_chat_turn`/`ChatOrchestrator` open
    short, per-round transactions) — this endpoint doesn't take a DB `Depends`."""
    async with rls_connection(auth.claims) as conn:
        session = await ChatRepo(conn).get_session(session_id)
        if session is None or session.user_id != auth.user_id:
            raise NotFoundError(f"Sesja czatu {session_id!r} nie istnieje.")
        if should_conflict_chat_send(
            live_task=is_turn_in_progress(session_id),
            db_flag=session.turn_in_progress,
            retry=payload.retry,
        ):
            raise ConflictError(
                "Trwa już tura czatu. Poczekaj na koniec albo anuluj."
            )

    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def _run_and_cleanup() -> None:
        try:
            await run_chat_turn(
                user_id=auth.user_id,
                claims=auth.claims,
                session_id=session_id,
                user_message=payload.content,
                queue=queue,
                retry=payload.retry,
            )
        finally:
            mark_turn_finished(session_id)

    orchestrator_task = asyncio.create_task(_run_and_cleanup())
    mark_turn_started(session_id, orchestrator_task)

    async def event_generator():
        try:
            loop = asyncio.get_event_loop()
            deadline = loop.time() + settings.chat_hard_timeout_s
            while True:
                if await request.is_disconnected():
                    # The turn continues in the background — the user can come back and refresh history.
                    break
                remaining = deadline - loop.time()
                if remaining <= 0:
                    orchestrator_task.cancel()
                    yield {"event": "error", "data": '{"code":"timeout","message":"Przekroczono limit czasu odpowiedzi."}'}
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=min(15, remaining))
                except asyncio.TimeoutError:
                    continue  # sse-starlette itself sends the ping (heartbeat)
                yield event
                if event["event"] in ("done", "error"):
                    break
        finally:
            pass

    return EventSourceResponse(event_generator(), ping=15)
