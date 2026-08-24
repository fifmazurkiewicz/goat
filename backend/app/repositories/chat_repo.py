"""`ChatRepo` — tables `chat_sessions`/`chat_messages` (ADR-13: 'persona'/'general' sessions,
`persona_id`/`invoked_via` attribution per message).

Same pattern as `PersonasRepo`. Tables are strictly `user_id = auth.uid()` in RLS (no
"community" like personas) — read methods deliberately do NOT add a redundant
`WHERE user_id`; RLS already enforces this (see `PersonasRepo` for the full rationale
for this convention).

**Tool-call representation without schema changes** (migrations 0001-0006 are frozen):
the `chat_messages.tool_calls jsonb` column is reused in two ways depending on `role`:
- `role='assistant'`: `{"calls": [{"id","type":"function","function":{"name","arguments"}}]}`
  — raw tool_calls list from the model response, to rebuild the OpenAI format for
  subsequent rounds.
- `role='tool'`: `{"tool_call_id": "..."}` — the only extra field needed to rebuild
  the correct `{"role":"tool","tool_call_id":...,"content":...}` contract when building
  history (OpenAI/OpenRouter tool message format).
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
        """Auto-title from the first user message — does not overwrite manual edits."""
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
        """FULL history (no windowing) — used by `GET /chat/sessions/{id}/messages`."""
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
        """Sliding window of the last `limit` messages (architecture.md §5), with
        per-persona filtering for `general` sessions (§3a pt 6): all
        `role='user'` + `role in ('assistant','tool')` WHERE `persona_id = X` — otherwise
        persona X would "see" other personas' replies as its own."""
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
        rows.reverse()  # chronological order for the model API
        return rows

    async def get_last_responding_persona(self, session_id: str) -> str | None:
        """Routing fallback in a `general` session (architecture.md §3a pt 3) — persona
        that last responded in this session."""
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
        """Last user message — used on `retry` (skip duplicate INSERT)."""
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
