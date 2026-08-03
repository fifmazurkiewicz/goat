"""`AllowedMetricsRepo` — tabela referencyjna `allowed_metrics` (database-schema.md).

Read-only, publiczna (RLS SELECT dla wszystkich). Ładowana do cache in-memory na
starcie appki (`app/domain/results/metrics_cache.py`) — hot-path w trakcie streamingu
SSE, nie chcemy zapytania SQL per `log_result` tool call."""

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
