"""`PlansRepo` — tabele `plans`/`plan_items`/`plan_generation_jobs`/
`plan_generation_job_personas` (architecture.md §4, ADR-1/2, database-schema.md).

Wzorzec jak `PersonasRepo`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.exceptions import ConflictError, NotFoundError

_PLAN_COLUMNS = "id, user_id, period_type, start_date, end_date, status, created_at, updated_at"
_ITEM_COLUMNS = "id, plan_id, item_date, item_type, persona_id, content, schema_version, created_at"
_JOB_COLUMNS = "id, plan_id, user_id, status, error_message, attempts, created_at, started_at, finished_at"
_JOB_PERSONA_COLUMNS = "job_id, persona_id, status, retry_count, last_error"


@dataclass(frozen=True, slots=True)
class PlanRow:
    id: str
    user_id: str
    period_type: str
    start_date: date
    end_date: date
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlanItemRow:
    id: str
    plan_id: str
    item_date: date
    item_type: str
    persona_id: str
    content: dict[str, Any]
    schema_version: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PlanJobRow:
    id: str
    plan_id: str
    user_id: str
    status: str
    error_message: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class PlanJobPersonaRow:
    job_id: str
    persona_id: str
    status: str
    retry_count: int
    last_error: str | None


def _row_to_item(row: Any) -> PlanItemRow:
    mapping = dict(row._mapping)
    if isinstance(mapping.get("content"), str):
        mapping["content"] = json.loads(mapping["content"])
    return PlanItemRow(**mapping)


class PlansRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    # ---------- plans ----------

    async def create_plan(
        self, *, user_id: str, period_type: str, start_date: date, end_date: date
    ) -> PlanRow:
        result = await self._conn.execute(
            text(
                f"""
                INSERT INTO plans (user_id, period_type, start_date, end_date, status)
                VALUES (:user_id, :period_type, :start_date, :end_date, 'generating')
                RETURNING {_PLAN_COLUMNS}
                """
            ),
            {
                "user_id": user_id,
                "period_type": period_type,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return PlanRow(**result.one()._mapping)

    async def get_plan(self, plan_id: str) -> PlanRow | None:
        result = await self._conn.execute(
            text(f"SELECT {_PLAN_COLUMNS} FROM plans WHERE id = :id"), {"id": plan_id}
        )
        row = result.one_or_none()
        return PlanRow(**row._mapping) if row is not None else None

    async def get_plan_for_date(self, target_date: date) -> PlanRow | None:
        """`GET /plans/{date}` — plan obejmujący dany dzień."""
        result = await self._conn.execute(
            text(
                f"""
                SELECT {_PLAN_COLUMNS} FROM plans
                WHERE start_date <= :target_date AND end_date >= :target_date
                ORDER BY created_at DESC LIMIT 1
                """
            ),
            {"target_date": target_date},
        )
        row = result.one_or_none()
        return PlanRow(**row._mapping) if row is not None else None

    async def list_plans_overlapping(self, *, range_start: date, range_end: date) -> list[PlanRow]:
        """`GET /plans?month=` — wszystkie plany nachodzące na podany zakres dat."""
        result = await self._conn.execute(
            text(
                f"""
                SELECT {_PLAN_COLUMNS} FROM plans
                WHERE start_date <= :range_end AND end_date >= :range_start
                ORDER BY start_date
                """
            ),
            {"range_start": range_start, "range_end": range_end},
        )
        return [PlanRow(**row._mapping) for row in result]

    async def update_plan_status(self, plan_id: str, status: str) -> None:
        await self._conn.execute(
            text("UPDATE plans SET status = :status, updated_at = now() WHERE id = :id"),
            {"id": plan_id, "status": status},
        )

    # ---------- plan_items ----------

    async def list_items_for_plan(self, plan_id: str) -> list[PlanItemRow]:
        result = await self._conn.execute(
            text(
                f"SELECT {_ITEM_COLUMNS} FROM plan_items WHERE plan_id = :plan_id "
                "ORDER BY item_date, created_at"
            ),
            {"plan_id": plan_id},
        )
        return [_row_to_item(row) for row in result]

    async def insert_items(self, plan_id: str, items: list[dict[str, Any]]) -> list[PlanItemRow]:
        inserted: list[PlanItemRow] = []
        for item in items:
            result = await self._conn.execute(
                text(
                    f"""
                    INSERT INTO plan_items (plan_id, item_date, item_type, persona_id, content)
                    VALUES (:plan_id, :item_date, :item_type, :persona_id, CAST(:content AS jsonb))
                    RETURNING {_ITEM_COLUMNS}
                    """
                ),
                {
                    "plan_id": plan_id,
                    "item_date": item["item_date"],
                    "item_type": item["item_type"],
                    "persona_id": item["persona_id"],
                    "content": json.dumps(item["content"]),
                },
            )
            inserted.append(_row_to_item(result.one()))
        return inserted

    async def update_item_content(self, item_id: str, content: dict[str, Any]) -> None:
        """Targeted patch etapu 3 — harmonizacja (architecture.md §4) koryguje TYLKO
        konkretne `plan_items`, nie pełna regeneracja."""
        await self._conn.execute(
            text("UPDATE plan_items SET content = CAST(:content AS jsonb) WHERE id = :id"),
            {"id": item_id, "content": json.dumps(content)},
        )

    # ---------- plan_generation_jobs ----------

    async def create_job(self, *, plan_id: str, user_id: str) -> PlanJobRow:
        """Rzuca `ConflictError` gdy user ma już aktywny job (`one_active_job_per_user`,
        partial unique index w bazie — ostateczna linia obrony przeciw race condition)."""
        try:
            result = await self._conn.execute(
                text(
                    f"""
                    INSERT INTO plan_generation_jobs (plan_id, user_id, status)
                    VALUES (:plan_id, :user_id, 'pending')
                    RETURNING {_JOB_COLUMNS}
                    """
                ),
                {"plan_id": plan_id, "user_id": user_id},
            )
        except IntegrityError as exc:
            raise ConflictError(
                "Masz już aktywny job generowania planu — poczekaj na zakończenie."
            ) from exc
        return PlanJobRow(**result.one()._mapping)

    async def get_job(self, job_id: str) -> PlanJobRow | None:
        result = await self._conn.execute(
            text(f"SELECT {_JOB_COLUMNS} FROM plan_generation_jobs WHERE id = :id"),
            {"id": job_id},
        )
        row = result.one_or_none()
        return PlanJobRow(**row._mapping) if row is not None else None

    async def update_job_status(
        self, job_id: str, status: str, *, error_message: str | None = None
    ) -> None:
        await self._conn.execute(
            text(
                """
                UPDATE plan_generation_jobs
                SET status = :status,
                    error_message = :error_message,
                    started_at = CASE
                        WHEN :status = 'running' AND started_at IS NULL THEN now()
                        ELSE started_at
                    END,
                    finished_at = CASE
                        WHEN :status IN ('success', 'partial_success', 'error') THEN now()
                        ELSE finished_at
                    END
                WHERE id = :id
                """
            ),
            {"id": job_id, "status": status, "error_message": error_message},
        )

    async def increment_attempts(self, job_id: str) -> None:
        await self._conn.execute(
            text("UPDATE plan_generation_jobs SET attempts = attempts + 1 WHERE id = :id"),
            {"id": job_id},
        )

    async def reap_stale_jobs(self, *, older_than_minutes: int) -> list[str]:
        """Reaper przy starcie appki (ADR-1): joby zawieszone (`pending`/`running`)
        starsze niż `older_than_minutes` -> `error`. Wymaga `service_role` (działa na
        WSZYSTKICH userach, nie jednym w kontekście RLS)."""
        result = await self._conn.execute(
            text(
                """
                UPDATE plan_generation_jobs
                SET status = 'error',
                    error_message = 'Job przerwany (restart serwera) — wygenerój plan ponownie.',
                    finished_at = now()
                WHERE status IN ('pending', 'running')
                  AND created_at < now() - make_interval(mins => :minutes)
                RETURNING id
                """
            ),
            {"minutes": older_than_minutes},
        )
        return [row.id for row in result]

    # ---------- plan_generation_job_personas ----------

    async def create_job_personas(self, job_id: str, persona_ids: list[str]) -> None:
        for persona_id in persona_ids:
            await self._conn.execute(
                text(
                    """
                    INSERT INTO plan_generation_job_personas (job_id, persona_id, status)
                    VALUES (:job_id, :persona_id, 'pending')
                    """
                ),
                {"job_id": job_id, "persona_id": persona_id},
            )

    async def update_job_persona_status(
        self,
        job_id: str,
        persona_id: str,
        status: str,
        *,
        last_error: str | None = None,
        increment_retry: bool = False,
    ) -> None:
        await self._conn.execute(
            text(
                """
                UPDATE plan_generation_job_personas
                SET status = :status,
                    last_error = :last_error,
                    retry_count = retry_count + CASE WHEN :increment_retry THEN 1 ELSE 0 END
                WHERE job_id = :job_id AND persona_id = :persona_id
                """
            ),
            {
                "job_id": job_id,
                "persona_id": persona_id,
                "status": status,
                "last_error": last_error,
                "increment_retry": increment_retry,
            },
        )

    async def list_job_personas(self, job_id: str) -> list[PlanJobPersonaRow]:
        result = await self._conn.execute(
            text(
                f"SELECT {_JOB_PERSONA_COLUMNS} FROM plan_generation_job_personas "
                "WHERE job_id = :job_id"
            ),
            {"job_id": job_id},
        )
        return [PlanJobPersonaRow(**row._mapping) for row in result]

    async def get_job_or_raise(self, job_id: str) -> PlanJobRow:
        job = await self.get_job(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id!r} nie istnieje.")
        return job
