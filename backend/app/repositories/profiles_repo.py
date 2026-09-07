"""`ProfilesRepo` — `profiles` table (1 row/user: `is_admin`, `is_approved`,
`max_active_personas`, `nick` — ADR-15, `usage_budget_usd` — ADR-16).

Same pattern as `PersonasRepo`. Used in the logged-in user's RLS context (`get`,
`update_nick`) and in `service_role` for `/admin/*` (`list_all`,
`update_max_active_personas`, `update_usage_budget`, `update_is_approved`) — the
latter operate on ALL users, hence explicit `WHERE id = :user_id` on updates (do not
rely on RLS, because `service_role` bypasses it).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.approval import is_auto_approved_email
from app.core.exceptions import NotFoundError
from app.repositories._row_utils import as_float, stringify_uuid

DEFAULT_MAX_ACTIVE_PERSONAS = 5
DEFAULT_USAGE_BUDGET_USD = 10.00

_COLUMNS = "id, is_admin, is_approved, max_active_personas, nick, usage_budget_usd, created_at"


@dataclass(frozen=True, slots=True)
class ProfileRow:
    id: str
    is_admin: bool
    is_approved: bool
    max_active_personas: int
    nick: str | None
    usage_budget_usd: float
    created_at: datetime


def _row_to_profile(row: Any) -> ProfileRow:
    mapping = dict(row._mapping)
    mapping["id"] = stringify_uuid(mapping["id"])
    mapping["usage_budget_usd"] = as_float(mapping["usage_budget_usd"])
    return ProfileRow(**mapping)


class ProfilesRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def get(self, user_id: str) -> ProfileRow | None:
        result = await self._conn.execute(
            text(f"SELECT {_COLUMNS} FROM profiles WHERE id = :user_id"),
            {"user_id": user_id},
        )
        row = result.one_or_none()
        return _row_to_profile(row) if row is not None else None

    async def list_all(self) -> list[ProfileRow]:
        """`/admin/users` — requires a `service_role` connection (RLS on `profiles` gives
        a regular user visibility only to their own row, see security.md)."""
        result = await self._conn.execute(text(f"SELECT {_COLUMNS} FROM profiles ORDER BY created_at DESC"))
        return [_row_to_profile(row) for row in result]

    async def update_max_active_personas(self, user_id: str, value: int) -> ProfileRow:
        """`PATCH /admin/users/{user_id}/persona-limit` (ADR-12). Range 0-50 is also
        enforced as a DB `CHECK` — Pydantic validation here is only faster, clearer
        feedback, NOT the sole barrier."""
        result = await self._conn.execute(
            text(
                f"""
                UPDATE profiles SET max_active_personas = :value
                WHERE id = :user_id
                RETURNING {_COLUMNS}
                """
            ),
            {"user_id": user_id, "value": value},
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError(f"Profil dla user_id={user_id!r} nie istnieje.")
        return _row_to_profile(row)

    async def update_usage_budget(self, user_id: str, value: float) -> ProfileRow:
        """`PATCH /admin/users/{user_id}/usage-budget` (ADR-16) — same pattern as
        `update_max_active_personas`."""
        result = await self._conn.execute(
            text(
                f"""
                UPDATE profiles SET usage_budget_usd = :value
                WHERE id = :user_id
                RETURNING {_COLUMNS}
                """
            ),
            {"user_id": user_id, "value": value},
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError(f"Profil dla user_id={user_id!r} nie istnieje.")
        return _row_to_profile(row)

    async def update_is_approved(self, user_id: str, is_approved: bool) -> ProfileRow:
        """`PATCH /admin/users/{user_id}/approval` (ADR-22) — boolean only; does not
        touch `usage_budget_usd` (default remains `DEFAULT_USAGE_BUDGET_USD`)."""
        result = await self._conn.execute(
            text(
                f"""
                UPDATE profiles SET is_approved = :is_approved
                WHERE id = :user_id
                RETURNING {_COLUMNS}
                """
            ),
            {"user_id": user_id, "is_approved": is_approved},
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError(f"Profil dla user_id={user_id!r} nie istnieje.")
        return _row_to_profile(row)

    async def ensure(self, user_id: str, email: str | None = None) -> ProfileRow:
        """Create a missing `profiles` row (e.g. after a DB wipe when auth.users remain).

        Call in `service_role` context — RLS on `profiles` has no INSERT policy for
        `authenticated` (created by the `handle_new_user` trigger on signup).

        `is_approved` is set only on INSERT (admin email → true, otherwise false).
        `ON CONFLICT DO NOTHING` leaves an existing row unchanged.
        """
        await self._conn.execute(
            text(
                """
                INSERT INTO profiles (id, is_approved)
                VALUES (:user_id, :is_approved)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"user_id": user_id, "is_approved": is_auto_approved_email(email)},
        )
        profile = await self.get(user_id)
        if profile is None:
            raise NotFoundError(f"Profil dla user_id={user_id!r} nie istnieje.")
        return profile

    async def update_nick(self, user_id: str, nick: str | None) -> ProfileRow:
        """`PATCH /account` (ADR-15) — in the user's own RLS context or service_role."""
        result = await self._conn.execute(
            text(
                f"""
                UPDATE profiles SET nick = :nick
                WHERE id = :user_id
                RETURNING {_COLUMNS}
                """
            ),
            {"user_id": user_id, "nick": nick},
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError(f"Profil dla user_id={user_id!r} nie istnieje.")
        return _row_to_profile(row)
