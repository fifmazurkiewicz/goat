"""`ExercisesRepo` — `exercises` table (ADR-14), reference content analogous to
`persona_templates`/`plan_templates` (`app/repositories/templates_repo.py`).

Read-only (RLS SELECT for everyone, no INSERT/UPDATE/DELETE outside migrations/seed) —
deliberately WITHOUT a separate `domain/exercises/` (ADR-14): filtering by `persona_type`/
`category`/`query` is simple `WHERE` logic, not business rules worth a dedicated domain layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_COLUMNS = (
    "id, slug, name, name_en, persona_type, level, categories, short_description, "
    "detail_full, common_mistakes, photo_path"
)


@dataclass(frozen=True, slots=True)
class ExerciseRow:
    id: str
    slug: str
    name: str
    name_en: str | None
    persona_type: str
    level: str
    categories: list[str]
    short_description: str
    detail_full: str
    common_mistakes: str | None
    photo_path: str | None


class ExercisesRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def list_all(
        self,
        *,
        persona_type: str | None = None,
        category: str | None = None,
        query: str | None = None,
    ) -> list[ExerciseRow]:
        """`GET /exercises` — optional, combinable filters (AND). `query` is a simple
        `ILIKE` on name (the search UI may also filter client-side on the full list —
        the catalog is small, ADR-14 — but server-side filter is cheap and limits payload
        if the catalog grows later)."""
        clauses: list[str] = []
        params: dict[str, object] = {}
        if persona_type is not None:
            clauses.append("persona_type = :persona_type")
            params["persona_type"] = persona_type
        if category is not None:
            clauses.append(":category = ANY(categories)")
            params["category"] = category
        if query is not None:
            clauses.append("name ILIKE :query")
            params["query"] = f"%{query}%"

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        result = await self._conn.execute(
            text(f"SELECT {_COLUMNS} FROM exercises {where} ORDER BY name"),
            params,
        )
        return [ExerciseRow(**row._mapping) for row in result]
