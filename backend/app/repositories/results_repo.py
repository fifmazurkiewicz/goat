"""`ResultsRepo` — `results` table (database-schema.md, ADR-9 trend charts).

Same pattern as `PersonasRepo`. RLS is strictly `user_id = auth.uid()` — read methods
deliberately do NOT add a redundant `WHERE user_id`; mutations (`update`/`delete`) add it
explicitly (see `PersonasRepo` for the full convention rationale)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.exceptions import NotFoundError
from app.repositories._row_utils import normalize_row_mapping

_COLUMNS = (
    "id, user_id, category, metric, value, unit, logged_date, source, source_persona_id, is_custom, notes, created_at"
)

_UUID_KEYS = ("id", "user_id", "source_persona_id")
_FLOAT_KEYS = ("value",)


@dataclass(frozen=True, slots=True)
class ResultRow:
    id: str
    user_id: str
    category: str
    metric: str
    value: float
    unit: str | None
    logged_date: date
    source: str
    source_persona_id: str | None
    is_custom: bool
    notes: str | None
    created_at: datetime


def _row_to_result(row: Any) -> ResultRow:
    mapping = normalize_row_mapping(dict(row._mapping), uuid_keys=_UUID_KEYS, float_keys=_FLOAT_KEYS)
    return ResultRow(**mapping)


class ResultsRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def list_for_user(
        self,
        *,
        category: str | None = None,
        metric: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ResultRow]:
        clauses = []
        params: dict[str, object] = {}
        if category is not None:
            clauses.append("category = :category")
            params["category"] = category
        if metric is not None:
            clauses.append("metric = :metric")
            params["metric"] = metric
        if date_from is not None:
            clauses.append("logged_date >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            clauses.append("logged_date <= :date_to")
            params["date_to"] = date_to

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        result = await self._conn.execute(
            text(f"SELECT {_COLUMNS} FROM results {where} ORDER BY logged_date DESC, created_at DESC"),
            params,
        )
        return [_row_to_result(row) for row in result]

    async def list_recent_for_user(self, *, limit: int = 12) -> list[ResultRow]:
        result = await self._conn.execute(
            text(f"SELECT {_COLUMNS} FROM results ORDER BY logged_date DESC, created_at DESC LIMIT :limit"),
            {"limit": limit},
        )
        return [_row_to_result(row) for row in result]

    async def create(self, user_id: str, values: dict[str, object]) -> ResultRow:
        columns = ["user_id", *values.keys()]
        placeholders = [":user_id", *(f":{key}" for key in values.keys())]
        result = await self._conn.execute(
            text(
                f"""
                INSERT INTO results ({", ".join(columns)})
                VALUES ({", ".join(placeholders)})
                RETURNING {_COLUMNS}
                """
            ),
            {"user_id": user_id, **values},
        )
        return _row_to_result(result.one())

    async def create_many(self, user_id: str, entries: list[dict[str, object]]) -> list[ResultRow]:
        return [await self.create(user_id, entry) for entry in entries]

    async def update(self, result_id: str, user_id: str, values: dict[str, object]) -> ResultRow:
        if not values:
            existing = await self.get_own(result_id, user_id)
            if existing is None:
                raise NotFoundError(f"Wynik {result_id!r} nie istnieje.")
            return existing
        set_clause = ", ".join(f"{key} = :{key}" for key in values.keys())
        result = await self._conn.execute(
            text(
                f"""
                UPDATE results SET {set_clause}
                WHERE id = :id AND user_id = :user_id
                RETURNING {_COLUMNS}
                """
            ),
            {"id": result_id, "user_id": user_id, **values},
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError(f"Wynik {result_id!r} nie istnieje lub nie należy do usera.")
        return _row_to_result(row)

    async def get_own(self, result_id: str, user_id: str) -> ResultRow | None:
        result = await self._conn.execute(
            text(f"SELECT {_COLUMNS} FROM results WHERE id = :id AND user_id = :user_id"),
            {"id": result_id, "user_id": user_id},
        )
        row = result.one_or_none()
        return _row_to_result(row) if row is not None else None

    async def delete(self, result_id: str, user_id: str) -> None:
        result = await self._conn.execute(
            text("DELETE FROM results WHERE id = :id AND user_id = :user_id RETURNING id"),
            {"id": result_id, "user_id": user_id},
        )
        if result.one_or_none() is None:
            raise NotFoundError(f"Wynik {result_id!r} nie istnieje lub nie należy do usera.")

    async def list_recent_for_planner(self, *, category: str | None, limit: int = 30) -> list[ResultRow]:
        """Last N entries (optionally per category) — planner context
        (architecture.md §5: "deterministic query of the last N records, without
        LLM summarization")."""
        where = "WHERE category = :category" if category else ""
        params = {"category": category} if category else {}
        result = await self._conn.execute(
            text(f"SELECT {_COLUMNS} FROM results {where} ORDER BY logged_date DESC, created_at DESC LIMIT :limit"),
            {**params, "limit": limit},
        )
        return [_row_to_result(row) for row in result]
