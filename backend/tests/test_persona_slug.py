"""Tests for persona `slug` generation / collision (ADR-13)."""

from __future__ import annotations

from app.domain.personas.service import generate_base_slug, resolve_slug_collision


def test_generate_base_slug_sanitizes_and_lowercases() -> None:
    assert generate_base_slug("personal_trainer", "Trener Kuba!") == "personal_trainer_trener_kuba"


def test_generate_base_slug_falls_back_when_empty() -> None:
    assert generate_base_slug("custom", "!!!") == "custom"


def test_resolve_slug_collision_returns_base_when_free() -> None:
    assert resolve_slug_collision("coach_kuba", set()) == "coach_kuba"


def test_resolve_slug_collision_appends_numeric_suffix() -> None:
    existing = {"coach_kuba", "coach_kuba_2"}
    assert resolve_slug_collision("coach_kuba", existing) == "coach_kuba_3"


def test_resolve_slug_collision_first_available_suffix() -> None:
    existing = {"coach_kuba", "coach_kuba_3"}
    # "_2" free even though "_3" is taken — we look for the first free number, not max+1.
    assert resolve_slug_collision("coach_kuba", existing) == "coach_kuba_2"
