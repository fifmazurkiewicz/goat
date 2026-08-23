"""`ExercisesRepo` — tabela `exercises` (ADR-14), treść referencyjna analogiczna do
`persona_templates`/`plan_templates` (`app/repositories/templates_repo.py`).

Read-only (RLS SELECT dla wszystkich, brak INSERT/UPDATE/DELETE poza migracjami/seedem) —
świadomie BEZ własnego `domain/exercises/` (ADR-14): filtrowanie po `persona_type`/
`category`/`query` to proste `WHERE`, bez reguł biznesowych wartych osobnej warstwy domenowej.
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
        """`GET /exercises` — filtry opcjonalne, kombinowalne (AND). `query` to prosty
        `ILIKE` po nazwie (wyszukiwarka może równie dobrze filtrować po stronie klienta
        na pełnej liście — katalog jest mały, ADR-14 — ale filtr server-side jest tani
        i ogranicza payload przy większym katalogu w przyszłości)."""
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
