"""Testy helperów planów — wybór planu dla zakresu kalendarza."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.repositories.plans_repo import PlanRow, pick_best_plan_for_range


def _plan(
    *,
    plan_id: str,
    status: str,
    created_at: datetime,
    start: date = date(2026, 8, 3),
    end: date = date(2026, 8, 9),
) -> PlanRow:
    return PlanRow(
        id=plan_id,
        user_id="user-1",
        period_type="week",
        start_date=start,
        end_date=end,
        status=status,
        created_at=created_at,
        updated_at=created_at,
    )


def test_pick_best_plan_prefers_newest_generating_over_older_ready() -> None:
    older = _plan(plan_id="a", status="ready", created_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    newer = _plan(plan_id="b", status="generating", created_at=datetime(2026, 8, 2, tzinfo=timezone.utc))

    picked = pick_best_plan_for_range([older, newer])

    assert picked is not None
    assert picked.id == "b"


def test_pick_best_plan_newest_when_same_status() -> None:
    older = _plan(plan_id="a", status="ready", created_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    newer = _plan(plan_id="b", status="ready", created_at=datetime(2026, 8, 3, tzinfo=timezone.utc))

    picked = pick_best_plan_for_range([older, newer])

    assert picked is not None
    assert picked.id == "b"


def test_pick_best_plan_empty_returns_none() -> None:
    assert pick_best_plan_for_range([]) is None


def test_harmonization_schema_supports_delete_action() -> None:
    from app.domain.plans.orchestrator import _harmonization_schema

    schema = _harmonization_schema(["pid-1", "pid-2"])
    props = schema["schema"]["properties"]["patches"]["items"]["properties"]
    assert props["action"]["enum"] == ["update", "delete"]
    assert "action" in schema["schema"]["properties"]["patches"]["items"]["required"]
