"""Kontrakt `GET /chat/sessions/{id}/messages` — widoczność konsultacji (2026-08-22).

FE paruje `role='tool'` z wywołaniami `consult_persona` w wiadomości Goata po
`tool_call_id` — wymaga więc, żeby API zwracało pole `tool_calls` (jsonb z DB).
Regresja: bez tego pola panel „{persona} odpowiedział" nigdy się nie renderował
po refetchu historii (root cause zgłoszenia 2026-08-22).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _row(
    *,
    id: str,
    role: str,
    content: str | None,
    tool_calls: dict[str, object] | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = id
    row.session_id = "s1"
    row.role = role
    row.content = content
    row.tool_calls = tool_calls
    row.persona_id = None
    row.invoked_via = None
    row.created_at = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
    return row


@pytest.fixture
def _patched(monkeypatch: pytest.MonkeyPatch):
    """Fake repo + RLS + auth dla routera list_chat_messages."""

    @asynccontextmanager
    async def fake_rls(_claims: object):
        yield MagicMock()

    class FakeChatRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def get_session(self, session_id: str):
            session = MagicMock()
            session.id = session_id
            session.user_id = "u1"
            return session

        async def list_messages(self, _session_id: str):
            return [
                _row(id="m1", role="assistant", content="", tool_calls={
                    "calls": [{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "consult_persona",
                            "arguments": '{"slug": "motoryka", "question": "q"}',
                        },
                    }]
                }),
                _row(id="m2", role="tool",
                     content=json.dumps({
                         "status": "ok", "slug": "motoryka",
                         "persona_label": "Bartek · Trener motoryczny",
                         "question": "q", "answer": "a",
                     }),
                     tool_calls={"tool_call_id": "call-1"}),
                _row(id="m3", role="assistant", content="Synteza Goata."),
            ]

    monkeypatch.setattr("app.api.routers.chat.rls_connection", fake_rls)
    monkeypatch.setattr("app.api.routers.chat.ChatRepo", FakeChatRepo)

    async def fake_auth() -> object:
        claims = {"sub": "u1"}
        ctx = MagicMock()
        ctx.claims = claims
        ctx.user_id = "u1"
        return ctx

    from app.core.security import get_current_user
    app.dependency_overrides[get_current_user] = fake_auth
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_messages_endpoint_returns_tool_calls(_patched) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/chat/sessions/s1/messages")
    assert res.status_code == 200
    messages = res.json()
    assistant_with_call = next(m for m in messages if m["id"] == "m1")
    assert assistant_with_call["tool_calls"] is not None
    calls = assistant_with_call["tool_calls"]["calls"]
    assert calls[0]["function"]["name"] == "consult_persona"
    tool_msg = next(m for m in messages if m["id"] == "m2")
    assert tool_msg["tool_calls"] == {"tool_call_id": "call-1"}
