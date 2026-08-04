"""`ChatRepo` — tabele `chat_sessions`/`chat_messages` (ADR-13: sesje 'persona'/'general',
atrybucja `persona_id`/`invoked_via` per wiadomość).

Wzorzec jak `PersonasRepo`. Tabele są ściśle `user_id = auth.uid()` w RLS (brak
"community" jak przy personach) — metody odczytu świadomie NIE dodają zbędnego
`WHERE user_id`, RLS już to egzekwuje (patrz `PersonasRepo` dla pełnego uzasadnienia
tej konwencji).

**Reprezentacja tool calls bez zmiany schematu** (migracje 0001-0006 są zamrożone):
kolumna `chat_messages.tool_calls jsonb` jest reużywana dwojako w zależności od `role`:
- `role='assistant'`: `{"calls": [{"id","type":"function","function":{"name","arguments"}}]}`
  — surowa lista tool_calls z odpowiedzi modelu, do odtworzenia formatu OpenAI przy
  budowaniu historii dla kolejnych rund.
- `role='tool'`: `{"tool_call_id": "..."}` — jedyne dodatkowe pole potrzebne, żeby
  odtworzyć poprawny kontrakt `{"role":"tool","tool_call_id":...,"content":...}` przy
  budowaniu historii (OpenAI/OpenRouter tool message format).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories._row_utils import stringify_uuid


@dataclass(frozen=True, slots=True)
class ChatSessionRow:
    id: str
    user_id: str
    persona_id: str | None
    session_type: str
    title: str | None
    turn_in_progress: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChatMessageRow:
    id: str
    session_id: str
    role: str
    content: str | None
    tool_calls: dict[str, Any] | None
    persona_id: str | None
    invoked_via: str | None
    created_at: datetime


_SESSION_UUID_KEYS = ("id", "user_id", "persona_id")
_MESSAGE_UUID_KEYS = ("id", "session_id", "persona_id")


def _row_to_session(row: Any) -> ChatSessionRow:
    mapping = dict(row._mapping)
    for key in _SESSION_UUID_KEYS:
        if key in mapping:
            mapping[key] = stringify_uuid(mapping[key])
    if "turn_in_progress" not in mapping:
        mapping["turn_in_progress"] = False
    return ChatSessionRow(**mapping)


def _row_to_message(row: Any) -> ChatMessageRow:
    mapping = dict(row._mapping)
    for key in _MESSAGE_UUID_KEYS:
        if key in mapping:
            mapping[key] = stringify_uuid(mapping[key])
    if isinstance(mapping.get("tool_calls"), str):
        mapping["tool_calls"] = json.loads(mapping["tool_calls"])
    return ChatMessageRow(**mapping)


_MESSAGE_COLUMNS = "id, session_id, role, content, tool_calls, persona_id, invoked_via, created_at"


class ChatRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    # ---------- sessions ----------

    async def create_session(
        self,
        *,
        user_id: str,
        persona_id: str | None,
        session_type: str,
        title: str | None,
    ) -> ChatSessionRow:
        result = await self._conn.execute(
            text(
                """
                INSERT INTO chat_sessions (user_id, persona_id, session_type, title)
                VALUES (:user_id, :persona_id, :session_type, :title)
                RETURNING id, user_id, persona_id, session_type, title, turn_in_progress, created_at, updated_at
                """
            ),
            {
                "user_id": user_id,
                "persona_id": persona_id,
                "session_type": session_type,
                "title": title,
            },
        )
        return _row_to_session(result.one())

    async def list_sessions(self) -> list[ChatSessionRow]:
        result = await self._conn.execute(
            text(
                """
                SELECT id, user_id, persona_id, session_type, title, turn_in_progress, created_at, updated_at
                FROM chat_sessions
                ORDER BY updated_at DESC
                """
            )
        )
        return [_row_to_session(row) for row in result]

    async def get_session(self, session_id: str) -> ChatSessionRow | None:
        result = await self._conn.execute(
            text(
                """
                SELECT id, user_id, persona_id, session_type, title, turn_in_progress, created_at, updated_at
                FROM chat_sessions WHERE id = :id
                """
            ),
            {"id": session_id},
        )
        row = result.one_or_none()
        return _row_to_session(row) if row is not None else None

    async def touch_session(self, session_id: str) -> None:
        await self._conn.execute(
            text("UPDATE chat_sessions SET updated_at = now() WHERE id = :id"),
            {"id": session_id},
        )

    async def update_session_title(self, session_id: str, title: str) -> ChatSessionRow | None:
        result = await self._conn.execute(
            text(
                """
                UPDATE chat_sessions SET title = :title, updated_at = now()
                WHERE id = :id
                RETURNING id, user_id, persona_id, session_type, title, turn_in_progress, created_at, updated_at
                """
            ),
            {"id": session_id, "title": title},
        )
        row = result.one_or_none()
        return _row_to_session(row) if row is not None else None

    async def set_title_if_empty(self, session_id: str, title: str) -> None:
        """Auto-tytuł z pierwszej wiadomości usera — nie nadpisuje ręcznej edycji."""
        await self._conn.execute(
            text(
                """
                UPDATE chat_sessions
                SET title = :title, updated_at = now()
                WHERE id = :id AND (title IS NULL OR trim(title) = '')
                """
            ),
            {"id": session_id, "title": title[:200]},
        )

    async def set_turn_in_progress(self, session_id: str, in_progress: bool) -> None:
        await self._conn.execute(
            text(
                "UPDATE chat_sessions SET turn_in_progress = :flag, updated_at = now() WHERE id = :id"
            ),
            {"id": session_id, "flag": in_progress},
        )

    async def delete_session(self, session_id: str) -> bool:
        result = await self._conn.execute(
            text("DELETE FROM chat_sessions WHERE id = :id RETURNING id"),
            {"id": session_id},
        )
        return result.one_or_none() is not None

    # ---------- messages ----------

    async def list_messages(self, session_id: str) -> list[ChatMessageRow]:
        """Historia PEŁNA (bez windowingu) — używana przez `GET /chat/sessions/{id}/messages`."""
        result = await self._conn.execute(
            text(
                f"SELECT {_MESSAGE_COLUMNS} FROM chat_messages "
                "WHERE session_id = :session_id ORDER BY created_at ASC"
            ),
            {"session_id": session_id},
        )
        return [_row_to_message(row) for row in result]

    async def list_recent_messages_for_context(
        self, *, session_id: str, persona_id: str | None, session_type: str, limit: int
    ) -> list[ChatMessageRow]:
        """Sliding window ostatnich `limit` wiadomości (architecture.md §5), z
        filtrowaniem per-personę dla sesji `general` (§3a pkt 6): wszystkie
        `role='user'` + `role in ('assistant','tool')` WHERE `persona_id = X` — inaczej
        persona X "widziałaby" odpowiedzi innych person jako własne."""
        if session_type == "general" and persona_id is not None:
            result = await self._conn.execute(
                text(
                    f"""
                    SELECT {_MESSAGE_COLUMNS} FROM chat_messages
                    WHERE session_id = :session_id
                      AND (role = 'user' OR persona_id = :persona_id)
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"session_id": session_id, "persona_id": persona_id, "limit": limit},
            )
        else:
            result = await self._conn.execute(
                text(
                    f"""
                    SELECT {_MESSAGE_COLUMNS} FROM chat_messages
                    WHERE session_id = :session_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"session_id": session_id, "limit": limit},
            )
        rows = [_row_to_message(row) for row in result]
        rows.reverse()  # chronologiczna kolejność dla API modelu
        return rows

    async def get_last_responding_persona(self, session_id: str) -> str | None:
        """Fallback routingu w sesji `general` (architecture.md §3a pkt 3) — persona,
        która ostatnio odpowiadała w tej sesji."""
        result = await self._conn.execute(
            text(
                """
                SELECT persona_id FROM chat_messages
                WHERE session_id = :session_id AND role = 'assistant' AND persona_id IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"session_id": session_id},
        )
        row = result.one_or_none()
        return stringify_uuid(row.persona_id) if row is not None else None

    async def get_last_user_message(self, session_id: str) -> ChatMessageRow | None:
        """Ostatnia wiadomość usera — używane przy `retry` (pomijanie podwójnego INSERT)."""
        result = await self._conn.execute(
            text(
                f"""
                SELECT {_MESSAGE_COLUMNS} FROM chat_messages
                WHERE session_id = :session_id AND role = 'user'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"session_id": session_id},
        )
        row = result.one_or_none()
        return _row_to_message(row) if row is not None else None

    async def insert_user_message(
        self,
        *,
        session_id: str,
        content: str,
        persona_id: str | None = None,
        invoked_via: str | None = None,
    ) -> ChatMessageRow:
        result = await self._conn.execute(
            text(
                f"""
                INSERT INTO chat_messages (session_id, role, content, persona_id, invoked_via)
                VALUES (:session_id, 'user', :content, :persona_id, :invoked_via)
                RETURNING {_MESSAGE_COLUMNS}
                """
            ),
            {
                "session_id": session_id,
                "content": content,
                "persona_id": persona_id,
                "invoked_via": invoked_via,
            },
        )
        return _row_to_message(result.one())

    async def insert_assistant_message(
        self,
        *,
        session_id: str,
        content: str | None,
        tool_calls: list[dict[str, Any]] | None,
        persona_id: str | None,
    ) -> ChatMessageRow:
        tool_calls_json = json.dumps({"calls": tool_calls}) if tool_calls else None
        result = await self._conn.execute(
            text(
                f"""
                INSERT INTO chat_messages (session_id, role, content, tool_calls, persona_id)
                VALUES (:session_id, 'assistant', :content, CAST(:tool_calls AS jsonb), :persona_id)
                RETURNING {_MESSAGE_COLUMNS}
                """
            ),
            {
                "session_id": session_id,
                "content": content,
                "tool_calls": tool_calls_json,
                "persona_id": persona_id,
            },
        )
        return _row_to_message(result.one())

    async def insert_tool_message(
        self, *, session_id: str, tool_call_id: str, content: str, persona_id: str | None
    ) -> ChatMessageRow:
        result = await self._conn.execute(
            text(
                f"""
                INSERT INTO chat_messages (session_id, role, content, tool_calls, persona_id)
                VALUES (:session_id, 'tool', :content, CAST(:tool_calls AS jsonb), :persona_id)
                RETURNING {_MESSAGE_COLUMNS}
                """
            ),
            {
                "session_id": session_id,
                "content": content,
                "tool_calls": json.dumps({"tool_call_id": tool_call_id}),
                "persona_id": persona_id,
            },
        )
        return _row_to_message(result.one())
