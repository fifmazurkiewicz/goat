"""Cache in-memory `allowed_metrics` + walidacja wpisów `results`/`log_result`.

Patrz docs/technical/database-schema.md (`allowed_metrics`), docs/technical/ai-pipeline.md
sekcja 2 (`log_result` batch, walidacja per-entry) i docs/technical/security.md sekcja 3
(sanity checks, fallback `is_custom=true`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

_MAX_UNIT_LENGTH = 20
_MAX_NOTES_LENGTH = 500
_APP_TZ = ZoneInfo("Europe/Warsaw")


def _today_warsaw() -> date:
    return datetime.now(_APP_TZ).date()


class AllowedMetricsRepositoryProtocol(Protocol):
    async def list_all(self) -> list[object]: ...


@dataclass(frozen=True, slots=True)
class MetricValidationResult:
    ok: bool
    is_custom: bool
    error: str | None
    normalized_unit: str | None


class AllowedMetricsCache:
    """Nie zna FastAPI/HTTP — testowalna z listą fake wierszy przekazaną do `load_rows`."""

    def __init__(self) -> None:
        self._metrics: dict[tuple[str, str], object] = {}

    async def load(self, repo: AllowedMetricsRepositoryProtocol) -> None:
        rows = await repo.list_all()
        self.load_rows(rows)

    def load_rows(self, rows: list) -> None:  # noqa: ANN401 — AllowedMetricRow duck-typed
        self._metrics = {(row.category, row.metric_key): row for row in rows}

    def get(self, category: str, metric_key: str) -> object | None:
        return self._metrics.get((category, metric_key))

    def validate_entry(
        self,
        *,
        category: str,
        metric: str,
        value: float,
        unit: str | None,
        notes: str | None,
        logged_date: date,
    ) -> MetricValidationResult:
        """Sanity checks (security.md §3) uniwersalne + walidacja zakresu/typu jeśli
        metryka jest znana w `allowed_metrics`, inaczej fallback `is_custom=True`."""
        if not isinstance(value, int | float) or not math.isfinite(value):
            return MetricValidationResult(False, True, "Wartość musi być skończoną liczbą.", unit)
        if unit is not None and len(unit) > _MAX_UNIT_LENGTH:
            return MetricValidationResult(
                False, True, f"Jednostka może mieć maks. {_MAX_UNIT_LENGTH} znaków.", unit
            )
        if notes is not None and len(notes) > _MAX_NOTES_LENGTH:
            return MetricValidationResult(
                False, True, f"Notatka może mieć maks. {_MAX_NOTES_LENGTH} znaków.", unit
            )
        if logged_date > _today_warsaw():
            return MetricValidationResult(False, True, "Data nie może być z przyszłości.", unit)

        allowed = self.get(category, metric)
        if allowed is None:
            return MetricValidationResult(True, True, None, unit)

        if allowed.value_type == "integer" and float(value) != int(value):
            return MetricValidationResult(
                False, False, f"Metryka '{metric}' wymaga liczby całkowitej.", allowed.unit
            )
        if allowed.value_min is not None and value < allowed.value_min:
            return MetricValidationResult(
                False, False, f"Wartość poniżej minimum ({allowed.value_min}) dla '{metric}'.", allowed.unit
            )
        if allowed.value_max is not None and value > allowed.value_max:
            return MetricValidationResult(
                False, False, f"Wartość powyżej maksimum ({allowed.value_max}) dla '{metric}'.", allowed.unit
            )
        return MetricValidationResult(True, False, None, allowed.unit)


allowed_metrics_cache = AllowedMetricsCache()
