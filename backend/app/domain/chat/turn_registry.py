"""Registry of active chat turns — survives SSE disconnects (Render Free, single instance)."""

from __future__ import annotations

import asyncio
from typing import Any

_active: dict[str, asyncio.Task[Any]] = {}


def mark_turn_started(session_id: str, task: asyncio.Task[Any]) -> None:
    old = _active.get(session_id)
    if old is not None and not old.done():
        old.cancel()
    _active[session_id] = task


def mark_turn_finished(session_id: str) -> None:
    _active.pop(session_id, None)


def is_turn_in_progress(session_id: str) -> bool:
    task = _active.get(session_id)
    return task is not None and not task.done()


def should_conflict_chat_send(*, live_task: bool, db_flag: bool, retry: bool) -> bool:
    """Live in-process turn always 409. Retry only for a DB orphan (no live task)."""
    if live_task:
        return True
    return db_flag and not retry


def cancel_turn(session_id: str) -> bool:
    """Cancels the active turn (Stop button) — stops LLM generation."""
    task = _active.get(session_id)
    if task is None or task.done():
        return False
    task.cancel()
    return True
