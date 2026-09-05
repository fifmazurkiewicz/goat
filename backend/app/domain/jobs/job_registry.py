"""Registry of in-process plan generation tasks — same pattern as chat `turn_registry`."""

from __future__ import annotations

import asyncio
from typing import Any

_active: dict[str, asyncio.Task[Any]] = {}


def mark_job_started(job_id: str, task: asyncio.Task[Any]) -> None:
    old = _active.get(job_id)
    if old is not None and not old.done():
        old.cancel()
    _active[job_id] = task


def mark_job_finished(job_id: str) -> None:
    _active.pop(job_id, None)


def is_job_in_progress(job_id: str) -> bool:
    task = _active.get(job_id)
    return task is not None and not task.done()


def cancel_job(job_id: str) -> bool:
    """Cancels the in-process `_run` task so it cannot finish as success."""
    task = _active.get(job_id)
    if task is None or task.done():
        return False
    task.cancel()
    return True
