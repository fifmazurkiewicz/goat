"""Testy schematu odpowiedzi joba generowania planu."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.schemas import PlanGenerationJobOut


def test_plan_generation_job_out_exposes_job_id_alias() -> None:
    now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
    out = PlanGenerationJobOut(
        id="job-uuid",
        plan_id="plan-uuid",
        status="pending",
        error_message=None,
        attempts=0,
        personas=[],
        created_at=now,
        started_at=None,
        finished_at=None,
    )

    assert out.job_id == "job-uuid"
    assert out.id == "job-uuid"
