"""`ProfilesRepo` — tabela `profiles` (1 wiersz/user: `is_admin`, `max_active_personas`).

Wzorzec jak `PersonasRepo` (patrz ten plik dla pełnego opisu konwencji). Używane w DWÓCH
miejscach o różnym kontekście połączenia:
1. `require_admin` (app/core/security.py) — odczyt `is_admin` w kontekście RLS zalogowanego
   usera (user widzi wyłącznie WŁASNY wiersz `profiles`, co wystarcza do sprawdzenia siebie).
2. `PersonaService.assert_can_activate_persona` — odczyt `max_active_personas` per user,
   też w kontekście RLS tego usera (patrz ADR-12).
3. `/admin/*` (service_role, `profiles_all_admin` — RLS nie ogranicza) — `list_all` i
   `update_max_active_personas` operują na WSZYSTKICH userach, stąd jawny filtr
   `WHERE id = :user_id` w update (nie polegamy na RLS, bo service_role je omija).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.exceptions import NotFoundError

DEFAULT_MAX_ACTIVE_PERSONAS = 5


@dataclass(frozen=True, slots=True)
class ProfileRow:
    id: str
    is_admin: bool
    max_active_personas: int
    created_at: datetime


class ProfilesRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def get(self, user_id: str) -> ProfileRow | None:
        result = await self._conn.execute(
            text(
                """
                SELECT id, is_admin, max_active_personas, created_at
                FROM profiles
                WHERE id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        row = result.one_or_none()
        return ProfileRow(**row._mapping) if row is not None else None

    async def list_all(self) -> list[ProfileRow]:
        """`/admin/users` — wymaga połączenia `service_role` (RLS na `profiles` daje
        zwykłemu userowi widoczność wyłącznie własnego wiersza, patrz security.md)."""
        result = await self._conn.execute(
            text(
                """
                SELECT id, is_admin, max_active_personas, created_at
                FROM profiles
                ORDER BY created_at DESC
                """
            )
        )
        return [ProfileRow(**row._mapping) for row in result]

    async def update_max_active_personas(self, user_id: str, value: int) -> ProfileRow:
        """`PATCH /admin/users/{user_id}/persona-limit` (ADR-12). Zakres 0-50 egzekwowany
        DODATKOWO jako `CHECK` w bazie (`supabase/migrations/0003_...sql`) — walidacja
        Pydantic (`PersonaLimitUpdate`) tu jest tylko szybszym, czytelniejszym feedbackiem,
        NIE jedyną barierą (ten sam wzorzec co walidacja `log_result`/`update_user_profile`)."""
        result = await self._conn.execute(
            text(
                """
                UPDATE profiles
                SET max_active_personas = :value
                WHERE id = :user_id
                RETURNING id, is_admin, max_active_personas, created_at
                """
            ),
            {"user_id": user_id, "value": value},
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError(f"Profil dla user_id={user_id!r} nie istnieje.")
        return ProfileRow(**row._mapping)
