"""Testy `resolve_persona_columns` — merge kolumn planu (persona.template_overrides
nadpisuje plan_templates.default_columns), patrz database-schema.md i frontend.md §7."""

from __future__ import annotations

from app.domain.personas.service import resolve_persona_columns


def test_uses_default_columns_when_no_overrides() -> None:
    persona = {"template_overrides": None}
    template = {"default_columns": ["Ćwiczenie", "Serie", "Powtórzenia"]}

    assert resolve_persona_columns(persona, template) == ["Ćwiczenie", "Serie", "Powtórzenia"]


def test_uses_default_columns_when_overrides_missing_columns_key() -> None:
    persona = {"template_overrides": {"other_key": True}}
    template = {"default_columns": ["Ćwiczenie", "Serie"]}

    assert resolve_persona_columns(persona, template) == ["Ćwiczenie", "Serie"]


def test_override_columns_replace_defaults_entirely() -> None:
    persona = {"template_overrides": {"columns": ["Posiłek", "Kcal"]}}
    template = {"default_columns": ["Ćwiczenie", "Serie", "Powtórzenia"]}

    assert resolve_persona_columns(persona, template) == ["Posiłek", "Kcal"]


def test_override_columns_deduplicated() -> None:
    persona = {"template_overrides": {"columns": ["A", "B", "A", "C"]}}

    assert resolve_persona_columns(persona, None) == ["A", "B", "C"]


def test_no_template_and_no_overrides_yields_empty_list() -> None:
    assert resolve_persona_columns({"template_overrides": None}, None) == []
