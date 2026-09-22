"""Tests for the plan-generation job response schema."""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.routers.plans import _job_phase
from app.models.schemas import PlanGenerationJobOut, PlanGenerationJobPersonaOut
from app.repositories.plans_repo import PlanJobRow


def test_plan_generation_job_out_exposes_job_id_alias() -> None:
    now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
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


def test_plan_job_phase_exposes_coordinator_personas_and_harmonization() -> None:
    now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
    job = PlanJobRow(
        id="job-uuid",
        plan_id="plan-uuid",
        user_id="user-uuid",
        status="running",
        error_message=None,
        attempts=1,
        created_at=now,
        started_at=now,
        finished_at=None,
    )
    pending = [PlanGenerationJobPersonaOut(persona_id="p1", status="pending", retry_count=0)]
    running = [PlanGenerationJobPersonaOut(persona_id="p1", status="running", retry_count=0)]
    done = [PlanGenerationJobPersonaOut(persona_id="p1", status="done", retry_count=0)]

    assert _job_phase(job, pending) == "coordinating"
    assert _job_phase(job, running) == "generating_personas"
    assert _job_phase(job, done) == "harmonizing"
