"""`UserProfileRepo` — tabela `user_profile` (jedna, WSPÓLNA na usera — patrz ADR-11,
docs/technical/ai-pipeline.md sekcja 0).

Wzorzec jak `PersonasRepo` (patrz ten plik dla pełnego opisu konwencji repozytoriów):
konstruktor przyjmuje wyłącznie `AsyncConnection` z już ustawionym kontekstem RLS,
metody to pojedyncze zapytania SQL z bindowanymi parametrami, zwracają typowany obiekt.

Zapisywana przez DWIE ścieżki, obie kończą się tym samym `upsert`:
1. Narzędzie `update_user_profile` wołane przez model w trakcie czatu (ChatOrchestrator).
2. `PATCH /api/v1/profile` — formularz, fallback dla userów niepreferujących rozmowy o danych.
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
        """`None` gdy user jeszcze nie ma wiersza (pierwsza rozmowa, przed jakąkolwiek
        aktualizacją) — `ContextBuilder` traktuje to tożsamo z "wszystkie pola puste"."""
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
        """Częściowa aktualizacja — `fields` to tylko klucze faktycznie podane przez
        wołającego (np. z `UserProfileUpdate.model_dump(exclude_unset=True)`), NIGDY
        pełny `model_dump()` (nadpisałby istniejące pola wartością `None`).

        `INSERT ... ON CONFLICT DO UPDATE` z `COALESCE` po stronie SQL byłoby kruche przy
        dynamicznym zbiorze kolumn — zamiast tego wołający scala z istniejącym wierszem
        (`get` + merge) w warstwie `PersonaService`/`ChatOrchestrator`, tu wchodzi już
        kompletny, docelowy zestaw wartości do zapisania.
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
