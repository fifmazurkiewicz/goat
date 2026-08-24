"""`PlansRepo` — tables `plans`/`plan_items`/`plan_generation_jobs`/
`plan_generation_job_personas` (architecture.md §4, ADR-1/2, database-schema.md).

Same pattern as `PersonasRepo`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.exceptions import ConflictError, NotFoundError
from app.repositories._row_utils import normalize_row_mapping

_PLAN_COLUMNS = "id, user_id, period_type, start_date, end_date, status, created_at, updated_at"
_ITEM_COLUMNS = "id, plan_id, item_date, item_type, persona_id, content, schema_version, created_at"
_JOB_COLUMNS = "id, plan_id, user_id, status, error_message, attempts, created_at, started_at, finished_at"
_JOB_PERSONA_COLUMNS = "job_id, persona_id, status, retry_count, last_error"

_PLAN_UUID_KEYS = ("id", "user_id")
_ITEM_UUID_KEYS = ("id", "plan_id", "persona_id")
_JOB_UUID_KEYS = ("id", "plan_id", "user_id")
_JOB_PERSONA_UUID_KEYS = ("job_id", "persona_id")


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


def _row_to_plan(row: Any) -> PlanRow:
    mapping = normalize_row_mapping(dict(row._mapping), uuid_keys=_PLAN_UUID_KEYS)
    return PlanRow(**mapping)


def _row_to_item(row: Any) -> PlanItemRow:
    mapping = normalize_row_mapping(dict(row._mapping), uuid_keys=_ITEM_UUID_KEYS)
    if isinstance(mapping.get("content"), str):
        mapping["content"] = json.loads(mapping["content"])
    return PlanItemRow(**mapping)


def _row_to_job(row: Any) -> PlanJobRow:
    mapping = normalize_row_mapping(dict(row._mapping), uuid_keys=_JOB_UUID_KEYS)
    return PlanJobRow(**mapping)


def _row_to_job_persona(row: Any) -> PlanJobPersonaRow:
    mapping = normalize_row_mapping(dict(row._mapping), uuid_keys=_JOB_PERSONA_UUID_KEYS)
    return PlanJobPersonaRow(**mapping)


_PLAN_STATUS_RANK = {"ready": 0, "partial_ready": 1, "generating": 2, "error": 3}


def pick_best_plan_for_range(plans: list[PlanRow]) -> PlanRow | None:
    """Pick the plan to show in the calendar — newest in range (regeneration visible immediately)."""
    if not plans:
        return None

    def sort_key(plan: PlanRow) -> tuple[float, int]:
        # Newest created_at first (e.g. fresh `generating` after regenerate),
        # then prefer ready on a timestamp tie.
        return (-plan.created_at.timestamp(), _PLAN_STATUS_RANK.get(plan.status, 9))

    return min(plans, key=sort_key)


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
        return _row_to_plan(result.one())

    async def get_plan(self, plan_id: str) -> PlanRow | None:
        result = await self._conn.execute(
            text(f"SELECT {_PLAN_COLUMNS} FROM plans WHERE id = :id"), {"id": plan_id}
        )
        row = result.one_or_none()
        return _row_to_plan(row) if row is not None else None

    async def get_latest_editable_plan_for_user(self, user_id: str) -> PlanRow | None:
        """Newest ready/partial_ready plan — chat edit (upsert_plan_items)."""
        result = await self._conn.execute(
            text(
                f"""
                SELECT {_PLAN_COLUMNS} FROM plans
                WHERE user_id = :user_id AND status IN ('ready', 'partial_ready')
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        )
        row = result.one_or_none()
        return _row_to_plan(row) if row is not None else None

    async def get_latest_plan_for_user(self, user_id: str) -> PlanRow | None:
        result = await self._conn.execute(
            text(
                f"""
                SELECT {_PLAN_COLUMNS} FROM plans
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        )
        row = result.one_or_none()
        return _row_to_plan(row) if row is not None else None

    async def get_item(self, item_id: str) -> PlanItemRow | None:
        result = await self._conn.execute(
            text(f"SELECT {_ITEM_COLUMNS} FROM plan_items WHERE id = :id"),
            {"id": item_id},
        )
        row = result.one_or_none()
        return _row_to_item(row) if row is not None else None

    async def get_plan_for_date(self, target_date: date) -> PlanRow | None:
        """`GET /plans/{date}` — plan covering the given day."""
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
        return _row_to_plan(row) if row is not None else None

    async def list_plans_overlapping(self, *, range_start: date, range_end: date) -> list[PlanRow]:
        """`GET /plans?start_date=&end_date=` — all plans overlapping the given date range."""
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
        return [_row_to_plan(row) for row in result]

    async def pick_plan_for_range(self, *, range_start: date, range_end: date) -> PlanRow | None:
        """Best plan for the visible calendar range — prefer ready, then newest."""
        plans = await self.list_plans_overlapping(range_start=range_start, range_end=range_end)
        return pick_best_plan_for_range(plans)

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
        """Single INSERTs — legacy; prefer `insert_items_batch`."""
        return await self.insert_items_batch(plan_id, items)

    async def insert_items_batch(self, plan_id: str, items: list[dict[str, Any]]) -> list[PlanItemRow]:
        """Batch INSERT of plan items — one round-trip per chunk (save per persona/period)."""
        if not items:
            return []

        inserted: list[PlanItemRow] = []
        chunk_size = 40
        for offset in range(0, len(items), chunk_size):
            chunk = items[offset : offset + chunk_size]
            value_parts: list[str] = []
            params: dict[str, Any] = {"plan_id": plan_id}
            for i, item in enumerate(chunk):
                value_parts.append(
                    f"(:plan_id, :date_{i}, :type_{i}, :persona_{i}, CAST(:content_{i} AS jsonb))"
                )
                params[f"date_{i}"] = item["item_date"]
                params[f"type_{i}"] = item["item_type"]
                params[f"persona_{i}"] = item["persona_id"]
                params[f"content_{i}"] = json.dumps(item["content"])
            result = await self._conn.execute(
                text(
                    f"""
                    INSERT INTO plan_items (plan_id, item_date, item_type, persona_id, content)
                    VALUES {", ".join(value_parts)}
                    RETURNING {_ITEM_COLUMNS}
                    """
                ),
                params,
            )
            inserted.extend(_row_to_item(row) for row in result)
        return inserted

    async def delete_items_for_persona(self, plan_id: str, persona_id: str) -> None:
        """Delete a persona's items — before regenerating a failed persona in the same job."""
        await self._conn.execute(
            text("DELETE FROM plan_items WHERE plan_id = :plan_id AND persona_id = :persona_id"),
            {"plan_id": plan_id, "persona_id": persona_id},
        )

    async def delete_item(self, item_id: str) -> None:
        """Delete a single item — e.g. Goat harmonization removes a card excluded by brief."""
        await self._conn.execute(
            text("DELETE FROM plan_items WHERE id = :id"),
            {"id": item_id},
        )

    async def update_item_content(self, item_id: str, content: dict[str, Any]) -> None:
        """Targeted stage-3 patch — harmonization (architecture.md §4) adjusts ONLY
        specific `plan_items`, not a full regeneration."""
        await self._conn.execute(
            text("UPDATE plan_items SET content = CAST(:content AS jsonb) WHERE id = :id"),
            {"id": item_id, "content": json.dumps(content)},
        )

    # ---------- plan_generation_jobs ----------

    async def create_job(self, *, plan_id: str, user_id: str) -> PlanJobRow:
        """Raises `ConflictError` when the user already has an active job (`one_active_job_per_user`,
        partial unique index in DB — final defense against race conditions)."""
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
        return _row_to_job(result.one())

    async def get_job(self, job_id: str) -> PlanJobRow | None:
        result = await self._conn.execute(
            text(f"SELECT {_JOB_COLUMNS} FROM plan_generation_jobs WHERE id = :id"),
            {"id": job_id},
        )
        row = result.one_or_none()
        return _row_to_job(row) if row is not None else None

    async def get_active_job_for_user(self, user_id: str) -> PlanJobRow | None:
        """Active job (`pending`/`running`) — max 1 per user (partial unique index)."""
        result = await self._conn.execute(
            text(
                f"""
                SELECT {_JOB_COLUMNS} FROM plan_generation_jobs
                WHERE user_id = :user_id AND status IN ('pending', 'running')
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        )
        row = result.one_or_none()
        return _row_to_job(row) if row is not None else None

    async def cancel_job(self, job_id: str) -> PlanJobRow:
        """Cancel the active job and mark the related plan as `error`."""
        job = await self.get_job(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id!r} nie istnieje.")
        if job.status not in ("pending", "running"):
            raise ConflictError("Ten job generowania planu nie jest już aktywny.")
        await self.update_job_status(
            job_id, "error", error_message="Anulowano przez użytkownika."
        )
        await self.update_plan_status(job.plan_id, "error")
        return await self.get_job_or_raise(job_id)

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
        """Reaper on app startup (ADR-1): jobs stuck in `pending`/`running`
        older than `older_than_minutes` -> `error`. Requires `service_role` (operates on
        ALL users, not one RLS context). Also updates `plans.status`."""
        result = await self._conn.execute(
            text(
                """
                UPDATE plan_generation_jobs
                SET status = 'error',
                    error_message = 'Job przerwany (restart serwera) — wygenerój plan ponownie.',
                    finished_at = now()
                WHERE status IN ('pending', 'running')
                  AND created_at < now() - make_interval(mins => :minutes)
                RETURNING id, plan_id
                """
            ),
            {"minutes": older_than_minutes},
        )
        rows = list(result)
        for row in rows:
            await self.update_plan_status(str(row.plan_id), "error")
        return [str(row.id) for row in rows]

    # ---------- plan_generation_job_personas ----------

    async def ensure_job_personas(self, job_id: str, persona_ids: list[str]) -> None:
        """Idempotent creation of per-persona rows (resume job without duplicate key)."""
        existing = {p.persona_id for p in await self.list_job_personas(job_id)}
        for persona_id in persona_ids:
            if persona_id in existing:
                continue
            await self._conn.execute(
                text(
                    """
                    INSERT INTO plan_generation_job_personas (job_id, persona_id, status)
                    VALUES (:job_id, :persona_id, 'pending')
                    """
                ),
                {"job_id": job_id, "persona_id": persona_id},
            )

    async def create_job_personas(self, job_id: str, persona_ids: list[str]) -> None:
        await self.ensure_job_personas(job_id, persona_ids)

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
        return [_row_to_job_persona(row) for row in result]

    async def get_job_or_raise(self, job_id: str) -> PlanJobRow:
        job = await self.get_job(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id!r} nie istnieje.")
        return job
