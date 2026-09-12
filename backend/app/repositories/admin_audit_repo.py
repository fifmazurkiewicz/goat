"""`AdminAuditRepo` — `admin_audit_log` table (database-schema.md, security.md §2).

Requires `service_role` (no RLS policies for `authenticated` on this table — `/admin/*` only,
see `supabase/migrations/0001_init.sql`)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_COLUMNS = "id, admin_user_id, action, target_user_id, details, created_at"


@dataclass(frozen=True, slots=True)
class AuditLogRow:
    id: str
    admin_user_id: str | None
    action: str
    target_user_id: str | None
    details: dict[str, Any] | None
    created_at: datetime


def _row_to_entry(row: Any) -> AuditLogRow:
    mapping = dict(row._mapping)
    if isinstance(mapping.get("details"), str):
        mapping["details"] = json.loads(mapping["details"])
    return AuditLogRow(**mapping)


class AdminAuditRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def log(
        self,
        *,
        admin_user_id: str,
        action: str,
        target_user_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        await self._conn.execute(
            text(
                """
                INSERT INTO admin_audit_log (admin_user_id, action, target_user_id, details)
                VALUES (:admin_user_id, :action, :target_user_id, CAST(:details AS jsonb))
                """
            ),
            {
                "admin_user_id": admin_user_id,
                "action": action,
                "target_user_id": target_user_id,
                "details": json.dumps(details) if details is not None else None,
            },
        )

    async def list_all(self, *, limit: int = 200) -> list[AuditLogRow]:
        result = await self._conn.execute(
            text(f"SELECT {_COLUMNS} FROM admin_audit_log ORDER BY created_at DESC LIMIT :limit"),
            {"limit": limit},
        )
        return [_row_to_entry(row) for row in result]
