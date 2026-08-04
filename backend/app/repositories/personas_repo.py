"""`PersonasRepo` — WZORZEC dla wszystkich przyszłych repozytoriów tego backendu.

Zasada (docs/technical/architecture.md sekcja 1 i 7): CAŁA wiedza SQL żyje w
`app/repositories/`, jako proste klasy przyjmujące `AsyncConnection` w konstruktorze —
NIE silnik/sesję. Połączenie jest już otwarte z ustawionym kontekstem RLS przez
`app.core.db.rls_connection(claims)` (sekcja 2 architecture.md) zanim trafi do repo.

Repo NIE zarządza transakcją samo (brak commit/rollback tutaj) — to odpowiedzialność
wołającego (orkiestrator/router), który otwiera `rls_connection` jako `async with`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.exceptions import NotFoundError
from app.repositories._row_utils import stringify_uuid

_SELECT_COLUMNS = """
    id, user_id, type, name, system_prompt, base_template_id,
    plan_template_id, template_overrides, detail_level, custom_result_category,
    persona_constraints, slug, is_shared, moderation_status,
    moderation_checked_prompt_hash, preamble_version, cloned_from_persona_id,
    active, created_at, updated_at
"""

_UUID_KEYS = (
    "id",
    "user_id",
    "base_template_id",
    "plan_template_id",
    "cloned_from_persona_id",
)


@dataclass(frozen=True, slots=True)
class PersonaRow:
    """Reprezentacja pełnego wiersza `personas` (patrz docs/technical/database-schema.md)."""

    id: str
    user_id: str
    type: str
    name: str
    system_prompt: str
    base_template_id: str | None
    plan_template_id: str | None
    template_overrides: dict[str, Any] | None
    detail_level: str
    custom_result_category: str | None
    persona_constraints: str | None
    slug: str
    is_shared: bool
    moderation_status: str
    moderation_checked_prompt_hash: str | None
    preamble_version: int
    cloned_from_persona_id: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


def _row_to_persona(row: Any) -> PersonaRow:
    mapping = dict(row._mapping)
    for key in _UUID_KEYS:
        if key in mapping:
            mapping[key] = stringify_uuid(mapping[key])
    overrides = mapping.get("template_overrides")
    if isinstance(overrides, str):
        mapping["template_overrides"] = json.loads(overrides)
    return PersonaRow(**mapping)


class PersonasRepo:
    """Repo tabeli `personas`.

    Metody odczytu widoczności (`list_for_user`, `get_visible`) celowo NIE dodają
    jawnego `WHERE user_id = :user_id` tam, gdzie RLS (`user_id = auth.uid() OR
    (is_shared AND moderation_status='approved')`) już egzekwuje to na poziomie
    Postgresa — patrz docs/technical/security.md sekcja 2 i ADR-3. Metody mutujące
    (`create`/`update`/`delete`) DODAJĄ `WHERE user_id = :user_id` mimo RLS — podwójna
    bariera jest tu tania i czyni intencję kodu jawną (nigdy nie edytujemy cudzej
    persony nawet gdyby RLS miało bug), a `RETURNING` z pustym wynikiem staje się
    czytelnym sygnałem "nie znaleziono/nie twoje" zamiast cichego no-opa.
    """

    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def list_for_user(self, user_id: str) -> list[PersonaRow]:
        """Wyłącznie WŁASNE persony usera (dla `/personas`, nie community)."""
        result = await self._conn.execute(
            text(f"SELECT {_SELECT_COLUMNS} FROM personas WHERE user_id = :user_id ORDER BY created_at DESC"),
            {"user_id": user_id},
        )
        return [_row_to_persona(row) for row in result]

    async def list_community(self, *, exclude_user_id: str) -> list[PersonaRow]:
        """`GET /personas/community` — persony innych userów, `is_shared` + `approved`.
        RLS już ogranicza SELECT do (własne) OR (shared+approved); tu dodatkowo
        wykluczamy własne, bo "community" ma sens jako "cudze do sklonowania"."""
        result = await self._conn.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS} FROM personas
                WHERE is_shared = true AND moderation_status = 'approved'
                  AND user_id <> :exclude_user_id
                ORDER BY created_at DESC
                """
            ),
            {"exclude_user_id": exclude_user_id},
        )
        return [_row_to_persona(row) for row in result]

    async def get_visible(self, persona_id: str) -> PersonaRow | None:
        """Jedna persona widoczna w kontekście RLS bieżącego usera (własna lub
        community approved) — używane przy odczycie do czatu/klonowania."""
        result = await self._conn.execute(
            text(f"SELECT {_SELECT_COLUMNS} FROM personas WHERE id = :id"),
            {"id": persona_id},
        )
        row = result.one_or_none()
        return _row_to_persona(row) if row is not None else None

    async def get_own(self, persona_id: str, user_id: str) -> PersonaRow | None:
        """Persona TYLKO jeśli należy do usera — do edycji/usuwania (nigdy cudza,
        nawet gdyby to była zaakceptowana community persona)."""
        result = await self._conn.execute(
            text(
                f"SELECT {_SELECT_COLUMNS} FROM personas WHERE id = :id AND user_id = :user_id"
            ),
            {"id": persona_id, "user_id": user_id},
        )
        row = result.one_or_none()
        return _row_to_persona(row) if row is not None else None

    async def list_slugs_for_user(self, user_id: str) -> set[str]:
        """Wszystkie sluggi usera — do rozwiązywania kolizji przy generowaniu (ADR-13)."""
        result = await self._conn.execute(
            text("SELECT slug FROM personas WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        return {row.slug for row in result}

    async def get_by_slug(self, user_id: str, slug: str) -> PersonaRow | None:
        """Lookup po `/slug` w sesji `general` (architecture.md §3a) — tylko aktywne."""
        result = await self._conn.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS} FROM personas
                WHERE user_id = :user_id AND slug = :slug AND active = true
                """
            ),
            {"user_id": user_id, "slug": slug},
        )
        row = result.one_or_none()
        return _row_to_persona(row) if row is not None else None

    async def list_active_for_user(self, user_id: str) -> list[PersonaRow]:
        """Aktywne persony usera — routing (ChatRoutingService) i generowanie planu."""
        result = await self._conn.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS} FROM personas
                WHERE user_id = :user_id AND active = true
                ORDER BY created_at ASC
                """
            ),
            {"user_id": user_id},
        )
        return [_row_to_persona(row) for row in result]

    async def count_active(self, user_id: str) -> int:
        """Liczba aktywnych person usera — wspiera limit per-konto
        (`profiles.max_active_personas`, ADR-12)."""
        result = await self._conn.execute(
            text(
                """
                SELECT count(*) AS active_count
                FROM personas
                WHERE user_id = :user_id AND active = true
                """
            ),
            {"user_id": user_id},
        )
        row = result.one()
        return int(row.active_count)

    async def create(self, user_id: str, values: dict[str, Any]) -> PersonaRow:
        columns = ["user_id", *values.keys()]
        # asyncpg + surowy `text()` nie wnioskuje jsonb z parametru — bez CAST
        # Postgres odrzuca text→jsonb (`template_overrides is of type jsonb but
        # expression is of type text`), co kończy się 500 przy create/update persony.
        placeholders = [
            ":user_id",
            *(
                f"CAST(:{key} AS jsonb)" if key == "template_overrides" else f":{key}"
                for key in values.keys()
            ),
        ]
        params: dict[str, Any] = {"user_id": user_id, **values}
        if "template_overrides" in params and params["template_overrides"] is not None:
            params["template_overrides"] = json.dumps(params["template_overrides"])
        result = await self._conn.execute(
            text(
                f"""
                INSERT INTO personas ({", ".join(columns)})
                VALUES ({", ".join(placeholders)})
                RETURNING {_SELECT_COLUMNS}
                """
            ),
            params,
        )
        return _row_to_persona(result.one())

    async def update(self, persona_id: str, user_id: str, values: dict[str, Any]) -> PersonaRow:
        if not values:
            existing = await self.get_own(persona_id, user_id)
            if existing is None:
                raise NotFoundError(f"Persona {persona_id!r} nie istnieje.")
            return existing

        params: dict[str, Any] = {"id": persona_id, "user_id": user_id, **values}
        if "template_overrides" in params and params["template_overrides"] is not None:
            params["template_overrides"] = json.dumps(params["template_overrides"])
        set_parts = [
            (
                f"{key} = CAST(:{key} AS jsonb)"
                if key == "template_overrides"
                else f"{key} = :{key}"
            )
            for key in values.keys()
        ]
        set_clause = ", ".join(set_parts)
        result = await self._conn.execute(
            text(
                f"""
                UPDATE personas
                SET {set_clause}, updated_at = now()
                WHERE id = :id AND user_id = :user_id
                RETURNING {_SELECT_COLUMNS}
                """
            ),
            params,
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError(f"Persona {persona_id!r} nie istnieje lub nie należy do usera.")
        return _row_to_persona(row)

    async def delete(self, persona_id: str, user_id: str) -> None:
        result = await self._conn.execute(
            text("DELETE FROM personas WHERE id = :id AND user_id = :user_id RETURNING id"),
            {"id": persona_id, "user_id": user_id},
        )
        if result.one_or_none() is None:
            raise NotFoundError(f"Persona {persona_id!r} nie istnieje lub nie należy do usera.")
