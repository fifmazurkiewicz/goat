"""`results.details` validation (ADR-25) — ordered [{label, value}] keyed by plan columns."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import LogResultArgs, ResultCreate


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
