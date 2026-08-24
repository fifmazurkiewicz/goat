"""Tests for the active chat-turn registry."""

from __future__ import annotations

import asyncio

import pytest

from app.domain.chat.turn_registry import cancel_turn, is_turn_in_progress, mark_turn_finished, mark_turn_started


@pytest.mark.asyncio
async def test_cancel_turn_stops_active_task() -> None:
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
    mark_turn_started("sess-1", task)
    await started.wait()

    assert is_turn_in_progress("sess-1")
    assert cancel_turn("sess-1") is True

    with pytest.raises(asyncio.CancelledError):
        await task

    assert cancelled.is_set()
    mark_turn_finished("sess-1")
    assert not is_turn_in_progress("sess-1")


def test_cancel_turn_false_when_no_task() -> None:
    assert cancel_turn("missing") is False