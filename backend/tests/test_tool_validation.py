"""Testy walidacji narzędzi LLM `log_result` i `update_user_profile` — niezaufany input
mimo że pochodzi z modelu (security.md §3), ADR-6 (batch, częściowy sukces)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.results.metrics_cache import AllowedMetricsCache
from app.domain.results.service import ResultsService
from app.models.schemas import LogResultArgs, UserProfileUpdate


# ============ LogResultArgs — walidacja schema-level ============


def test_log_result_args_requires_at_least_one_entry() -> None:
    with pytest.raises(ValidationError):
        LogResultArgs.model_validate({"entries": []})


def test_log_result_args_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        LogResultArgs.model_validate(
            {"entries": [{"category": "not_real", "metric": "x", "value": 1, "date": "2026-01-01"}]}
        )


def test_log_result_args_accepts_valid_entry() -> None:
    parsed = LogResultArgs.model_validate(
        {
            "entries": [
                {"category": "strength", "metric": "weight_kg", "value": 82.5, "date": "2026-01-01"}
            ]
        }
    )
    assert parsed.entries[0].value == 82.5


# ============ update_user_profile — walidacja zakresów (ai-pipeline.md §0) ============


def test_update_user_profile_rejects_height_out_of_range() -> None:
    with pytest.raises(ValidationError):
        UserProfileUpdate.model_validate({"height_cm": 5})


def test_update_user_profile_partial_update_only_sets_given_fields() -> None:
    parsed = UserProfileUpdate.model_validate({"weight_kg": 75})
    dumped = parsed.model_dump(exclude_unset=True)
    assert dumped == {"weight_kg": 75}


# ============ ResultsService.log_batch_from_agent — częściowy sukces (ADR-6) ============


@dataclass
class _FakeAllowedMetric:
    category: str
    metric_key: str
    unit: str
    value_type: str
    value_min: float | None
    value_max: float | None


class _FakeResultsRepo:
    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create(self, user_id: str, values: dict) -> dict:
        self.created.append(values)
        return values


def _metrics_cache() -> AllowedMetricsCache:
    cache = AllowedMetricsCache()
    cache.load_rows(
        [_FakeAllowedMetric("strength", "weight_kg", "kg", "numeric", 20, 400)]
    )
    return cache


async def test_log_batch_partial_success_valid_and_invalid_entries() -> None:
    repo = _FakeResultsRepo()
    service = ResultsService(repo, _metrics_cache())

    outcomes = await service.log_batch_from_agent(
        user_id="u1",
        source_persona_id="p1",
        entries=[
            {"category": "strength", "metric": "weight_kg", "value": 80, "logged_date": date(2026, 1, 1)},
            # Poza zakresem allowed_metrics (min 20) -> odrzucone, NIE wyjątek.
            {"category": "strength", "metric": "weight_kg", "value": 5, "logged_date": date(2026, 1, 1)},
        ],
    )

    assert outcomes[0].ok is True
    assert outcomes[1].ok is False
    assert len(repo.created) == 1


async def test_log_batch_unknown_metric_falls_back_to_custom() -> None:
    repo = _FakeResultsRepo()
    service = ResultsService(repo, _metrics_cache())

    outcomes = await service.log_batch_from_agent(
        user_id="u1",
        source_persona_id="p1",
        entries=[
            {"category": "custom", "metric": "vertical_jump_cm", "value": 55, "logged_date": date(2026, 1, 1)}
        ],
    )

    assert outcomes[0].ok is True
    assert repo.created[0]["is_custom"] is True


async def test_log_batch_accepts_null_source_persona_for_team_lead() -> None:
    """Goat (`team_lead`) nie ma UUID persony — wpis idzie z `source_persona_id=NULL`
    (spec 2026-08-17; kolumna nullable w `0001_init.sql`)."""
    repo = _FakeResultsRepo()
    service = ResultsService(repo, _metrics_cache())

    outcomes = await service.log_batch_from_agent(
        user_id="u1",
        source_persona_id=None,
        entries=[
            {
                "category": "strength",
                "metric": "weight_kg",
                "value": 80,
                "logged_date": date(2026, 1, 1),
            }
        ],
    )

    assert outcomes[0].ok is True
    assert repo.created[0]["source_persona_id"] is None
    assert repo.created[0]["source"] == "agent"


async def test_log_batch_missing_field_reported_as_error_not_exception() -> None:
    repo = _FakeResultsRepo()
    service = ResultsService(repo, _metrics_cache())

    outcomes = await service.log_batch_from_agent(
        user_id="u1", source_persona_id="p1", entries=[{"category": "strength"}]
    )

    assert outcomes[0].ok is False
    assert outcomes[0].error is not None
    assert repo.created == []
