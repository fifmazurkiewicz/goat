"""Tests for ContextBuilder — profile + temporal context (Europe/Warsaw)."""

from __future__ import annotations

from datetime import date

from app.domain.chat.context_builder import ContextBuilder, build_temporal_context_block


def test_temporal_context_includes_iso_date_and_warsaw() -> None:
    block = build_temporal_context_block(today=date(2026, 8, 4))
    assert "2026-08-04" in block
    assert "wtorek" in block
    assert "Europe/Warsaw" in block
    assert "log_result" in block


def test_system_prompt_starts_with_preamble_then_temporal() -> None:
    builder = ContextBuilder(_FakeRepo(), history_window_messages=10)
    prompt = builder.build_system_prompt(
        persona_type="motor_coach",
        persona_system_prompt="Bądź konkretny.",
        persona_constraints=None,
        user_profile=None,
    )
    assert "[KONTEKST CZASOWY]" in prompt
    assert "Europe/Warsaw" in prompt
    assert "[ZAKRES ROLI" in prompt
    assert prompt.index("[1. TOŻSAMOŚĆ") < prompt.index("[ZAKRES ROLI")
    assert prompt.index("[ZAKRES ROLI") < prompt.index("[KONTEKST CZASOWY]")


class _FakeRepo:
    async def list_recent_messages_for_context(self, **kwargs):  # noqa: ANN003
        return []
