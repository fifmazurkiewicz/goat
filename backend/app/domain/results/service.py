"""`ResultsService` — business logic for `results` (`allowed_metrics` validation, batch
write via `log_result`, manual CRUD). Shared by `/results` (manual) and
`ChatOrchestrator` (`log_result` tool, ai-pipeline.md section 2).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.results.metrics_cache import AllowedMetricsCache


class ResultsRepositoryProtocol(Protocol):
    async def list_for_user(self, **kwargs: Any) -> list[Any]: ...
    async def create(self, user_id: str, values: dict[str, Any]) -> Any: ...
    async def update(self, result_id: str, user_id: str, values: dict[str, Any]) -> Any: ...
    async def get_own(self, result_id: str, user_id: str) -> Any | None: ...
    async def delete(self, result_id: str, user_id: str) -> None: ...


class LogResultEntryOutcome:
    __slots__ = ("index", "ok", "error", "row")

    def __init__(self, index: int, ok: bool, error: str | None = None, row: Any = None) -> None:
        self.index = index
        self.ok = ok
        self.error = error
        self.row = row


class ResultsService:
    """Doesn't know FastAPI/HTTP — testable with a fake repo + `AllowedMetricsCache` (arch. §7)."""

    def __init__(self, results_repo: ResultsRepositoryProtocol, metrics_cache: AllowedMetricsCache) -> None:
        self._results_repo = results_repo
        self._metrics_cache = metrics_cache

    async def list_results(
        self,
        *,
        category: str | None = None,
        metric: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Any]:
        return await self._results_repo.list_for_user(
            category=category, metric=metric, date_from=date_from, date_to=date_to
        )

    async def create_manual(self, user_id: str, payload: dict[str, Any]) -> Any:
        """`POST /results` — manual entry (`source='manual'`). Metric outside
        `allowed_metrics` -> `is_custom=True` instead of an error (deliberate fallback,
        security.md §3); other sanity-check violations (finite number, field lengths,
        date) are ALWAYS rejected (`ValidationError` 400) regardless of whether the
        metric is known."""
        validation = self._metrics_cache.validate_entry(
            category=payload["category"],
            metric=payload["metric"],
            value=payload["value"],
            unit=payload.get("unit"),
            notes=payload.get("notes"),
            logged_date=payload["logged_date"],
        )
        if not validation.ok:
            raise ValidationError(validation.error or "Nieprawidłowy wpis wyniku.")

        values = {**payload, "source": "manual", "is_custom": validation.is_custom}
        if validation.normalized_unit is not None and not payload.get("unit"):
            values["unit"] = validation.normalized_unit
        return await self._results_repo.create(user_id, values)

    async def update_manual(self, result_id: str, user_id: str, updates: dict[str, Any]) -> Any:
        existing = await self._results_repo.get_own(result_id, user_id)
        if existing is None:
            raise NotFoundError(f"Wynik {result_id!r} nie istnieje.")

        merged = {
            "category": updates.get("category", existing.category),
            "metric": updates.get("metric", existing.metric),
            "value": updates.get("value", existing.value),
            "unit": updates.get("unit", existing.unit),
            "notes": updates.get("notes", existing.notes),
            "logged_date": updates.get("logged_date", existing.logged_date),
        }
        validation = self._metrics_cache.validate_entry(
            category=merged["category"],
            metric=merged["metric"],
            value=merged["value"],
            unit=merged["unit"],
            notes=merged["notes"],
            logged_date=merged["logged_date"],
        )
        if not validation.ok:
            raise ValidationError(validation.error or "Nieprawidłowy wpis wyniku.")

        values = {**updates, "is_custom": validation.is_custom}
        return await self._results_repo.update(result_id, user_id, values)

    async def delete_manual(self, result_id: str, user_id: str) -> None:
        await self._results_repo.delete(result_id, user_id)

    async def log_batch_from_agent(
        self, *, user_id: str, source_persona_id: str | None, entries: list[dict[str, Any]]
    ) -> list[LogResultEntryOutcome]:
        """`log_result` tool (ai-pipeline.md section 2, ADR-6) — validation PER ENTRY,
        partial success (3/5 pass, 2 return as an error in the same tool response,
        NOT as an exception — security.md section 3).

        `source_persona_id=None` = Goat's write (team lead is not a `personas` row)."""
        outcomes: list[LogResultEntryOutcome] = []
        for index, entry in enumerate(entries):
            try:
                validation = self._metrics_cache.validate_entry(
                    category=entry["category"],
                    metric=entry["metric"],
                    value=entry["value"],
                    unit=entry.get("unit"),
                    notes=entry.get("notes"),
                    logged_date=entry["logged_date"],
                )
            except (KeyError, TypeError) as exc:
                outcomes.append(LogResultEntryOutcome(index, False, f"Brakujące/nieprawidłowe pole: {exc}"))
                continue

            if not validation.ok:
                outcomes.append(LogResultEntryOutcome(index, False, validation.error))
                continue

            values = {
                "category": entry["category"],
                "metric": entry["metric"],
                "value": entry["value"],
                "unit": entry.get("unit") or validation.normalized_unit,
                "logged_date": entry["logged_date"],
                "notes": entry.get("notes"),
                "source": "agent",
                "source_persona_id": source_persona_id,
                "is_custom": validation.is_custom,
            }
            row = await self._results_repo.create(user_id, values)
            outcomes.append(LogResultEntryOutcome(index, True, row=row))

        return outcomes
