"""`UserProfileRepo` — `user_profile` table (one row SHARED per user — see ADR-11,
docs/technical/ai-pipeline.md section 0).

Same pattern as `PersonasRepo` (see that file for the full repository convention):
constructor takes only an `AsyncConnection` with RLS context already set,
methods are single SQL queries with bound parameters returning a typed object.

Saved via TWO paths, both ending in the same `upsert`:
1. `update_user_profile` tool called by the model during chat (ChatOrchestrator).
2. `PATCH /api/v1/profile` — form fallback for users who prefer not to discuss data in chat.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories._row_utils import normalize_row_mapping

_UUID_KEYS = ("user_id",)
_FLOAT_KEYS = ("height_cm", "weight_kg")


@dataclass(frozen=True, slots=True)
class UserProfileRow:
    user_id: str
    height_cm: float | None
    weight_kg: float | None
    date_of_birth: date | None
    sex: str | None
    activity_level: str | None
    primary_goal: str | None
    notes: str | None
    updated_at: datetime


def _row_to_profile(row: Any) -> UserProfileRow:
    mapping = normalize_row_mapping(dict(row._mapping), uuid_keys=_UUID_KEYS, float_keys=_FLOAT_KEYS)
    return UserProfileRow(**mapping)


class UserProfileRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def get(self, user_id: str) -> UserProfileRow | None:
        """`None` when the user has no row yet (first conversation, before any
        update) — `ContextBuilder` treats this the same as "all fields empty"."""
        result = await self._conn.execute(
            text(
                """
                SELECT user_id, height_cm, weight_kg, date_of_birth, sex,
                       activity_level, primary_goal, notes, updated_at
                FROM user_profile
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        row = result.one_or_none()
        return _row_to_profile(row) if row is not None else None

    async def upsert(self, user_id: str, fields: dict[str, object]) -> UserProfileRow:
        """Partial update — `fields` contains only keys actually provided by the
        caller (e.g. from `UserProfileUpdate.model_dump(exclude_unset=True)`), NEVER
        a full `model_dump()` (that would overwrite existing fields with `None`).

        `INSERT ... ON CONFLICT DO UPDATE` with SQL-side `COALESCE` would be fragile with
        a dynamic column set — instead the caller merges with the existing row
        (`get` + merge) in `PersonaService`/`ChatOrchestrator`; this layer receives the
        complete target values to persist.
        """
        columns = ", ".join(fields.keys())
        placeholders = ", ".join(f":{key}" for key in fields.keys())
        update_clause = ", ".join(f"{key} = :{key}" for key in fields.keys())
        result = await self._conn.execute(
            text(
                f"""
                INSERT INTO user_profile (user_id, {columns}, updated_at)
                VALUES (:user_id, {placeholders}, now())
                ON CONFLICT (user_id) DO UPDATE SET {update_clause}, updated_at = now()
                RETURNING user_id, height_cm, weight_kg, date_of_birth, sex,
                          activity_level, primary_goal, notes, updated_at
                """
            ),
            {"user_id": user_id, **fields},
        )
        return _row_to_profile(result.one())
