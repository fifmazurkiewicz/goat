"""In-process plan-job task registry (same pattern as chat turn_registry)."""

from __future__ import annotations

import asyncio

import pytest

from app.domain.jobs.job_registry import (
    cancel_job,
    is_job_in_progress,
    mark_job_finished,
    mark_job_started,
)


@pytest.mark.asyncio
async def test_cancel_job_stops_active_task() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _worker() -> None:
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    task = asyncio.create_task(_worker())
    mark_job_started("job-1", task)
    await started.wait()

    assert is_job_in_progress("job-1")
    assert cancel_job("job-1") is True

    with pytest.raises(asyncio.CancelledError):
        await task

    assert cancelled.is_set()
    mark_job_finished("job-1")
    assert not is_job_in_progress("job-1")


def test_cancel_job_false_when_no_task() -> None:
    assert cancel_job("missing") is False
