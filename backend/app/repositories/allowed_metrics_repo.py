"""`AllowedMetricsRepo` — reference table `allowed_metrics` (database-schema.md).

Read-only, public (RLS SELECT for everyone). Loaded into an in-memory cache on app
startup (`app/domain/results/metrics_cache.py`) — hot path during SSE streaming;
avoid one SQL query per `log_result` tool call."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True, slots=True)
class AllowedMetricRow:
    category: str
    metric_key: str
    unit: str
    value_type: str
    value_min: float | None
    value_max: float | None


class AllowedMetricsRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def list_all(self) -> list[AllowedMetricRow]:
        result = await self._conn.execute(
            text(
                "SELECT category, metric_key, unit, value_type, value_min, value_max "
                "FROM allowed_metrics"
            )
        )
        return [AllowedMetricRow(**row._mapping) for row in result]
