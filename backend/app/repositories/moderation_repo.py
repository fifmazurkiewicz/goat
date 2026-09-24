"""`ModerationEventsRepo` — `moderation_events` table (security.md section 1/GDPR).

IMPORTANT: `moderation_events` has no RLS policies for the `authenticated` role (no SELECT/INSERT) —
access only via `service_role` (see `supabase/migrations/0001_init.sql` and
docs/technical/database-schema.md, RLS section). This repo MUST receive a connection from
`app.core.db.service_role_connection()`, NEVER plain `rls_connection` — insert via
`authenticated` context is silently rejected by RLS (0 rows, no error from `INSERT` without
`RETURNING`, so the failure is easy to miss)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories._row_utils import normalize_row_mapping


@dataclass(frozen=True, slots=True)
class ModerationEventRow:
    id: str
    user_id: str
    persona_id: str | None
    session_id: str | None
    message_id: str | None
    trigger_type: str
    raw_snippet: str | None
    classifier_verdict: str | None
    reviewed: bool
    created_at: datetime


class ModerationEventsRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def log(
        self,
        *,
        user_id: str,
        trigger_type: str,
        persona_id: str | None = None,
        session_id: str | None = None,
        message_id: str | None = None,
        raw_snippet: str | None = None,
        classifier_verdict: str | None = None,
    ) -> None:
        await self._conn.execute(
            text(
                """
                INSERT INTO moderation_events
                    (user_id, persona_id, session_id, message_id, trigger_type,
                     raw_snippet, classifier_verdict)
                VALUES
                    (:user_id, :persona_id, :session_id, :message_id, :trigger_type,
                     :raw_snippet, :classifier_verdict)
                """
            ),
            {
                "user_id": user_id,
                "persona_id": persona_id,
                "session_id": session_id,
                "message_id": message_id,
                "trigger_type": trigger_type,
                "raw_snippet": raw_snippet,
                "classifier_verdict": classifier_verdict,
            },
        )

    async def list_all(self, *, limit: int = 200) -> list[ModerationEventRow]:
        """`/admin/audit-log`-adjacent read (extra visibility, not required by the API spec,
        but useful internally) — requires `service_role`."""
        result = await self._conn.execute(
            text(
                """
                SELECT id, user_id, persona_id, session_id, message_id, trigger_type,
                       raw_snippet, classifier_verdict, reviewed, created_at
                FROM moderation_events
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [
            ModerationEventRow(
                **normalize_row_mapping(
                    dict(row._mapping),
                    uuid_keys=("id", "user_id", "persona_id", "session_id", "message_id"),
                )
            )
            for row in result
        ]
