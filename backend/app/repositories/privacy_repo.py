"""Persistence for versioned consent, privacy exports and retention cleanup."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

HEALTH_CONSENT_VERSION = "health-v1-2026-09-12"
AI_DISCLOSURE_VERSION = "ai-v1-2026-09-12"
HEALTH_CONSENT_NOTICE = (
    "Wyrażam dobrowolną zgodę na przetwarzanie danych dotyczących zdrowia i sprawności "
    "w celu personalizacji coachingu, wyników i planów oraz na przekazywanie niezbędnego "
    "minimum treści dostawcy modelu AI. Zgodę mogę wycofać w każdej chwili."
)
AI_DISCLOSURE_NOTICE = (
    "Rozumiem, że rozmawiam z systemem AI, którego odpowiedzi mogą zawierać błędy i nie zastępują porady medycznej."
)


class PrivacyRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def active_consents(self, user_id: str) -> dict[str, dict[str, Any]]:
        result = await self._conn.execute(
            text("""
                SELECT consent_type, document_version, granted_at, notice_sha256
                FROM privacy_consents
                WHERE user_id = :user_id AND withdrawn_at IS NULL
            """),
            {"user_id": user_id},
        )
        return {
            str(row.consent_type): {
                "version": str(row.document_version),
                "granted_at": row.granted_at,
                "notice_sha256": str(row.notice_sha256),
            }
            for row in result
        }

    async def grant(self, user_id: str, consent_type: str, version: str, notice_text: str) -> None:
        # A changed notice/version requires a fresh affirmative action. Close a
        # stale active record first so the partial unique index permits the new
        # consent while preserving the complete audit history.
        await self._conn.execute(
            text("""
                UPDATE privacy_consents SET withdrawn_at = now()
                WHERE user_id = :user_id AND consent_type = :consent_type
                  AND withdrawn_at IS NULL AND document_version <> :version
            """),
            {"user_id": user_id, "consent_type": consent_type, "version": version},
        )
        await self._conn.execute(
            text("""
                INSERT INTO privacy_consents
                  (user_id, consent_type, document_version, notice_text, notice_sha256)
                SELECT :user_id, :consent_type, :version, :notice_text, :notice_sha256
                WHERE NOT EXISTS (
                  SELECT 1 FROM privacy_consents
                  WHERE user_id = :user_id AND consent_type = :consent_type
                    AND withdrawn_at IS NULL
                )
            """),
            {
                "user_id": user_id,
                "consent_type": consent_type,
                "version": version,
                "notice_text": notice_text,
                "notice_sha256": sha256(notice_text.encode("utf-8")).hexdigest(),
            },
        )

    async def withdraw_health(self, user_id: str) -> datetime | None:
        result = await self._conn.execute(
            text("""
                UPDATE privacy_consents SET withdrawn_at = now()
                WHERE user_id = :user_id AND consent_type = 'health_data'
                  AND withdrawn_at IS NULL
                RETURNING withdrawn_at
            """),
            {"user_id": user_id},
        )
        return result.scalar_one_or_none()

    async def export_user(self, user_id: str) -> dict[str, Any]:
        tables = {
            "account": ("SELECT * FROM profiles WHERE id = :user_id", True),
            "profile": ("SELECT * FROM user_profile WHERE user_id = :user_id", True),
            "personas": ("SELECT * FROM personas WHERE user_id = :user_id ORDER BY created_at", False),
            "chat_sessions": ("SELECT * FROM chat_sessions WHERE user_id = :user_id ORDER BY created_at", False),
            "chat_messages": (
                """SELECT m.* FROM chat_messages m
                   JOIN chat_sessions s ON s.id = m.session_id
                   WHERE s.user_id = :user_id ORDER BY m.created_at""",
                False,
            ),
            "results": ("SELECT * FROM results WHERE user_id = :user_id ORDER BY created_at", False),
            "plans": ("SELECT * FROM plans WHERE user_id = :user_id ORDER BY created_at", False),
            "plan_items": (
                """SELECT i.* FROM plan_items i
                   JOIN plans p ON p.id = i.plan_id
                   WHERE p.user_id = :user_id ORDER BY i.created_at""",
                False,
            ),
            "consents": ("SELECT * FROM privacy_consents WHERE user_id = :user_id ORDER BY created_at", False),
            "usage": ("SELECT * FROM usage_limits WHERE user_id = :user_id ORDER BY period_start", False),
            "plan_generation_jobs": (
                "SELECT * FROM plan_generation_jobs WHERE user_id = :user_id ORDER BY created_at",
                False,
            ),
            "background_jobs": ("SELECT * FROM background_jobs WHERE user_id = :user_id ORDER BY created_at", False),
        }
        exported: dict[str, Any] = {}
        for name, (query, single) in tables.items():
            rows = (await self._conn.execute(text(query), {"user_id": user_id})).mappings().all()
            values = [dict(row) for row in rows]
            exported[name] = (values[0] if values else None) if single else values
        return exported

    async def purge_expired(self, *, chat_days: int, job_days: int, moderation_days: int) -> dict[str, int]:
        chats = await self._conn.execute(
            text("DELETE FROM chat_sessions WHERE updated_at < now() - make_interval(days => :days) RETURNING id"),
            {"days": chat_days},
        )
        jobs = await self._conn.execute(
            text(
                """DELETE FROM background_jobs
                   WHERE created_at < now() - make_interval(days => :days)
                     AND status IN ('success', 'error') RETURNING id"""
            ),
            {"days": job_days},
        )
        plan_jobs = await self._conn.execute(
            text(
                """DELETE FROM plan_generation_jobs
                   WHERE finished_at < now() - make_interval(days => :days)
                     AND status IN ('success', 'partial_success', 'error') RETURNING id"""
            ),
            {"days": job_days},
        )
        snippets = await self._conn.execute(
            text(
                """UPDATE moderation_events SET raw_snippet = NULL
                   WHERE raw_snippet IS NOT NULL
                     AND created_at < now() - make_interval(days => :days) RETURNING id"""
            ),
            {"days": moderation_days},
        )
        return {
            "chat_sessions": len(chats.all()),
            "background_jobs": len(jobs.all()),
            "plan_generation_jobs": len(plan_jobs.all()),
            "moderation_snippets": len(snippets.all()),
        }
