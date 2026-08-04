"""`ProfilesRepo` — tabela `profiles` (1 wiersz/user: `is_admin`, `max_active_personas`,
`nick` — ADR-15, `usage_budget_usd` — ADR-16).

Wzorzec jak `PersonasRepo`. Używane w kontekście RLS zalogowanego usera (`get`,
`update_nick`) i w kontekście `service_role` dla `/admin/*` (`list_all`,
`update_max_active_personas`, `update_usage_budget`) — te ostatnie operują na
WSZYSTKICH userach, stąd jawny filtr `WHERE id = :user_id` w update (nie polegamy na
RLS, bo `service_role` je omija)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.exceptions import NotFoundError

DEFAULT_MAX_ACTIVE_PERSONAS = 5
DEFAULT_USAGE_BUDGET_USD = 10.00

_COLUMNS = "id, is_admin, max_active_personas, nick, usage_budget_usd, created_at"


@dataclass(frozen=True, slots=True)
class ProfileRow:
    id: str
    is_admin: bool
    max_active_personas: int
    nick: str | None
    usage_budget_usd: float
    created_at: datetime


class ProfilesRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def get(self, user_id: str) -> ProfileRow | None:
        result = await self._conn.execute(
            text(f"SELECT {_COLUMNS} FROM profiles WHERE id = :user_id"),
            {"user_id": user_id},
        )
        row = result.one_or_none()
        return ProfileRow(**row._mapping) if row is not None else None

    async def list_all(self) -> list[ProfileRow]:
        """`/admin/users` — wymaga połączenia `service_role` (RLS na `profiles` daje
        zwykłemu userowi widoczność wyłącznie własnego wiersza, patrz security.md)."""
        result = await self._conn.execute(
            text(f"SELECT {_COLUMNS} FROM profiles ORDER BY created_at DESC")
        )
        return [ProfileRow(**row._mapping) for row in result]

    async def update_max_active_personas(self, user_id: str, value: int) -> ProfileRow:
        """`PATCH /admin/users/{user_id}/persona-limit` (ADR-12). Zakres 0-50 egzekwowany
        DODATKOWO jako `CHECK` w bazie — walidacja Pydantic tu jest tylko szybszym,
        czytelniejszym feedbackiem, NIE jedyną barierą."""
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
        return ProfileRow(**row._mapping)

    async def update_usage_budget(self, user_id: str, value: float) -> ProfileRow:
        """`PATCH /admin/users/{user_id}/usage-budget` (ADR-16) — wzorzec identyczny
        jak `update_max_active_personas`."""
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
        return ProfileRow(**row._mapping)

    async def ensure(self, user_id: str) -> ProfileRow:
        """Tworzy brakujący wiersz `profiles` (np. po wipe DB gdy auth.users zostali).

        Wywoływać w kontekście `service_role` — RLS na `profiles` nie ma policy INSERT
        dla `authenticated` (tworzy je trigger `handle_new_user` przy rejestracji).
        """
        await self._conn.execute(
            text(
                """
                INSERT INTO profiles (id)
                VALUES (:user_id)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"user_id": user_id},
        )
        profile = await self.get(user_id)
        if profile is None:
            raise NotFoundError(f"Profil dla user_id={user_id!r} nie istnieje.")
        return profile

    async def update_nick(self, user_id: str, nick: str | None) -> ProfileRow:
        """`PATCH /account` (ADR-15) — w kontekście RLS własnego usera lub service_role."""
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
        return ProfileRow(**row._mapping)
