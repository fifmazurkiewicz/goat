"""`BackgroundJobsRepo` — `background_jobs` table (migration 0008).

Persistent job queue in Postgres: plan generation, harmonization after upsert,
auto chat title. Render Free = single instance; reaper/startup resumes pending jobs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories._row_utils import normalize_row_mapping

_JOB_COLUMNS = (
    "id, user_id, job_type, status, payload, error_message, attempts, "
    "created_at, started_at, finished_at"
)
_JOB_UUID_KEYS = ("id", "user_id")


@dataclass(frozen=True, slots=True)
class BackgroundJobRow:
    id: str
    user_id: str
    job_type: str
    status: str
    payload: dict[str, Any]
    error_message: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def _row_to_job(row: Any) -> BackgroundJobRow:
    mapping = normalize_row_mapping(dict(row._mapping), uuid_keys=_JOB_UUID_KEYS)
    if isinstance(mapping.get("payload"), str):
        mapping["payload"] = json.loads(mapping["payload"])
    return BackgroundJobRow(**mapping)


class BackgroundJobsRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def create(
        self, *, user_id: str, job_type: str, payload: dict[str, Any]
    ) -> BackgroundJobRow:
        result = await self._conn.execute(
            text(
                f"""
                INSERT INTO background_jobs (user_id, job_type, payload)
                VALUES (:user_id, :job_type, CAST(:payload AS jsonb))
                RETURNING {_JOB_COLUMNS}
                """
            ),
            {
                "user_id": user_id,
                "job_type": job_type,
                "payload": json.dumps(payload, default=str),
            },
        )
        return _row_to_job(result.one())

    async def get(self, job_id: str) -> BackgroundJobRow | None:
        result = await self._conn.execute(
            text(f"SELECT {_JOB_COLUMNS} FROM background_jobs WHERE id = :id"),
            {"id": job_id},
        )
        row = result.one_or_none()
        return _row_to_job(row) if row is not None else None

    async def mark_running(self, job_id: str) -> None:
        await self._conn.execute(
            text(
                """
                UPDATE background_jobs
                SET status = 'running',
                    attempts = attempts + 1,
                    started_at = COALESCE(started_at, now())
                WHERE id = :id
                """
            ),
            {"id": job_id},
        )

    async def mark_finished(
        self, job_id: str, *, status: str, error_message: str | None = None
    ) -> None:
        await self._conn.execute(
            text(
                """
                UPDATE background_jobs
                SET status = :status,
                    error_message = :error_message,
                    finished_at = now()
                WHERE id = :id
                """
            ),
            {"id": job_id, "status": status, "error_message": error_message},
        )

    async def list_resumable(self, *, limit: int = 20) -> list[BackgroundJobRow]:
        result = await self._conn.execute(
            text(
                f"""
                SELECT {_JOB_COLUMNS} FROM background_jobs
                WHERE status IN ('pending', 'running')
                ORDER BY created_at ASC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [_row_to_job(row) for row in result]

    async def reap_stale_running(self, *, older_than_minutes: int) -> list[str]:
        result = await self._conn.execute(
            text(
                """
                UPDATE background_jobs
                SET status = 'error',
                    error_message = 'Przekroczono limit czasu (reaper).',
                    finished_at = now()
                WHERE status = 'running'
                  AND started_at < now() - make_interval(mins => :mins)
                RETURNING id
                """
            ),
            {"mins": older_than_minutes},
        )
        return [str(row.id) for row in result]
