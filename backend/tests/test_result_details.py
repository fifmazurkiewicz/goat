"""`results.details` validation (ADR-25) — ordered [{label, value}] keyed by plan columns."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.domain.chat.tools import LOG_RESULT_TOOL_SCHEMA
from app.domain.results.metrics_cache import AllowedMetricsCache
from app.domain.results.service import ResultsService
from app.models.schemas import LogResultArgs, ResultCreate
from app.repositories.results_repo import _encode_values, _row_to_result


def _entry(details: object) -> dict[str, object]:
    return {"category": "strength", "metric": "Dead bug", "value": 50, "date": "2026-10-11", "details": details}


def test_details_accepts_ordered_cells_and_coerces_numbers() -> None:
    parsed = LogResultArgs.model_validate(
        {"entries": [_entry([{"label": " Ćwiczenie ", "value": "Dead bug"}, {"label": "Serie", "value": 3}])]}
    )
    cells = parsed.entries[0].details
    assert cells is not None
    assert [(c.label, c.value) for c in cells] == [("Ćwiczenie", "Dead bug"), ("Serie", "3")]


def test_details_rejects_duplicate_labels_case_insensitive() -> None:
    with pytest.raises(ValidationError):
        LogResultArgs.model_validate(
            {"entries": [_entry([{"label": "Serie", "value": "3"}, {"label": "serie", "value": "4"}])]}
        )


@pytest.mark.parametrize(
    "details",
    [
        [],
        [{"label": "", "value": "x"}],
        [{"label": "x" * 61, "value": "x"}],
        [{"label": "Serie", "value": "   "}],
        [{"label": "Serie", "value": "x" * 121}],
        [{"label": f"k{i}", "value": "v"} for i in range(13)],
    ],
)
def test_details_rejects_invalid_shapes(details: object) -> None:
    with pytest.raises(ValidationError):
        ResultCreate.model_validate(
            {"category": "strength", "metric": "m", "value": 1, "logged_date": "2026-10-11", "details": details}
        )


def test_details_is_optional() -> None:
    parsed = ResultCreate.model_validate(
        {"category": "strength", "metric": "m", "value": 1, "logged_date": "2026-10-11"}
    )
    assert parsed.details is None


# ============ Persistence and log_result ============


def test_row_to_result_parses_details_json_string() -> None:
    row = SimpleNamespace(
        _mapping={
            "id": "r1",
            "user_id": "u1",
            "category": "strength",
            "metric": "Dead bug",
            "value": 50,
            "unit": "kg",
            "logged_date": date(2026, 10, 11),
            "source": "agent",
            "source_persona_id": None,
            "is_custom": True,
            "notes": None,
            "created_at": date(2026, 10, 11),
            "details": json.dumps([{"label": "Serie", "value": "3"}]),
        }
    )
    assert _row_to_result(row).details == [{"label": "Serie", "value": "3"}]


def test_encode_values_serializes_details_only() -> None:
    encoded = _encode_values({"metric": "m", "details": [{"label": "Serie", "value": "3"}]})
    assert encoded["metric"] == "m"
    assert json.loads(str(encoded["details"])) == [{"label": "Serie", "value": "3"}]
    assert _encode_values({"details": None})["details"] is None


class _Repo:
    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create(self, user_id: str, values: dict) -> dict:
        self.created.append(values)
        return values


async def test_log_batch_passes_details_through() -> None:
    repo = _Repo()
    service = ResultsService(repo, AllowedMetricsCache())
    cells = [{"label": "Ćwiczenie", "value": "Dead bug"}, {"label": "Serie", "value": "3"}]
    outcomes = await service.log_batch_from_agent(
        user_id="u1",
        source_persona_id="p1",
        entries=[
            {
                "category": "strength",
                "metric": "Dead bug",
                "value": 50,
                "unit": "kg",
                "logged_date": date(2026, 10, 11),
                "details": cells,
            }
        ],
    )
    assert outcomes[0].ok is True
    assert repo.created[0]["details"] == cells


def test_log_result_tool_schema_exposes_optional_details() -> None:
    entry = LOG_RESULT_TOOL_SCHEMA["function"]["parameters"]["properties"]["entries"]["items"]
    details = entry["properties"]["details"]
    assert details["type"] == "array"
    assert details["items"]["required"] == ["label", "value"]
    assert "details" not in entry["required"]


def test_log_result_notes_are_scoped_to_the_entry() -> None:
    """Notes must not carry a summary of the whole workout (seen in prod 2026-10-10)."""
    entry = LOG_RESULT_TOOL_SCHEMA["function"]["parameters"]["properties"]["entries"]["items"]
    description = entry["properties"]["notes"]["description"]
    assert "TYLKO" in description
    assert "całego treningu" in description
