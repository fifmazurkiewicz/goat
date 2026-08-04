"""Rejestr aktywnych tur czatu — tło po rozłączeniu SSE (Render Free, jedna instancja)."""

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
