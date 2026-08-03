"""`ModerationEventsRepo` — tabela `moderation_events` (security.md sekcja 1/RODO).

WAŻNE: `moderation_events` nie ma polityk RLS dla roli `authenticated` (brak SELECT/INSERT) —
dostęp wyłącznie przez `service_role` (patrz `supabase/migrations/0001_init.sql` i
docs/technical/database-schema.md, sekcja RLS). Ten repo MUSI dostać połączenie z
`app.core.db.service_role_connection()`, NIGDY zwykłe `rls_connection` — insert przez
kontekst `authenticated` skończy się cichym odrzuceniem przez RLS (0 wierszy, brak błędu
z `INSERT` bez `RETURNING`, więc błąd byłby łatwy do przeoczenia)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True, slots=True)
class ModerationEventRow:
    id: str
    user_id: str
    trigger_type: str
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
        """`/admin/audit-log`-adjacent read (dodatkowy wgląd, nie wymagany przez spec API,
        ale przydatny wewnętrznie) — wymaga `service_role`."""
        result = await self._conn.execute(
            text(
                """
                SELECT id, user_id, trigger_type, classifier_verdict, reviewed, created_at
                FROM moderation_events
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [ModerationEventRow(**row._mapping) for row in result]
