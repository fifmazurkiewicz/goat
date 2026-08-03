"""Repozytoria "gotowców" — `persona_templates`/`plan_templates` (database-schema.md).

Tabele read-only dla usera (SELECT publiczne przez RLS), więc repo tu ma wyłącznie
metody odczytu. Wzorzec jak `PersonasRepo`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True, slots=True)
class PersonaTemplateRow:
    id: str
    type: str
    default_prompt: str
    label: str
    created_at: Any


@dataclass(frozen=True, slots=True)
class PlanTemplateRow:
    id: str
    name: str
    suggested_for: list[str]
    default_columns: list[str]
    default_rows: list[Any]
    created_at: Any


class PersonaTemplatesRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def list_all(self) -> list[PersonaTemplateRow]:
        result = await self._conn.execute(
            text(
                "SELECT id, type, default_prompt, label, created_at "
                "FROM persona_templates ORDER BY label"
            )
        )
        return [_row_to_persona_template(row) for row in result]

    async def get(self, template_id: str) -> PersonaTemplateRow | None:
        result = await self._conn.execute(
            text(
                "SELECT id, type, default_prompt, label, created_at "
                "FROM persona_templates WHERE id = :id"
            ),
            {"id": template_id},
        )
        row = result.one_or_none()
        return _row_to_persona_template(row) if row is not None else None

    async def get_safety_prompt(self, template_id: str) -> str | None:
        """Odczyt `app_private.persona_template_safety` — wołać wyłącznie na połączeniu
        `service_role` (brak GRANT dla anon/authenticated)."""
        result = await self._conn.execute(
            text(
                "SELECT safety_prompt FROM app_private.persona_template_safety "
                "WHERE template_id = :id"
            ),
            {"id": template_id},
        )
        row = result.one_or_none()
        return str(row.safety_prompt) if row is not None else None


class PlanTemplatesRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def list_all(self) -> list[PlanTemplateRow]:
        result = await self._conn.execute(
            text(
                "SELECT id, name, suggested_for, default_columns, default_rows, created_at "
                "FROM plan_templates ORDER BY name"
            )
        )
        return [_row_to_plan_template(row) for row in result]

    async def get(self, template_id: str) -> PlanTemplateRow | None:
        result = await self._conn.execute(
            text(
                "SELECT id, name, suggested_for, default_columns, default_rows, created_at "
                "FROM plan_templates WHERE id = :id"
            ),
            {"id": template_id},
        )
        row = result.one_or_none()
        return _row_to_plan_template(row) if row is not None else None


def _stringify_uuid(value: Any) -> Any:
    return str(value) if isinstance(value, UUID) else value


def _row_to_persona_template(row: Any) -> PersonaTemplateRow:
    mapping = dict(row._mapping)
    mapping["id"] = _stringify_uuid(mapping["id"])
    return PersonaTemplateRow(**mapping)


def _row_to_plan_template(row: Any) -> PlanTemplateRow:
    mapping = dict(row._mapping)
    mapping["id"] = _stringify_uuid(mapping["id"])
    for key in ("default_columns", "default_rows"):
        if isinstance(mapping.get(key), str):
            mapping[key] = json.loads(mapping[key])
    return PlanTemplateRow(**mapping)
