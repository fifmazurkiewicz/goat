"""Tests for `resolve_persona_columns` — merge of plan columns
(persona.template_overrides overrides plan_templates.default_columns),
see database-schema.md and frontend.md §7."""

from __future__ import annotations

from types import SimpleNamespace

from app.domain.personas.service import load_persona_columns, resolve_persona_columns
from app.models.schemas import PersonaOut


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


class _Templates:
    def __init__(self) -> None:
        self.calls = 0

    async def list_all(self) -> list[SimpleNamespace]:
        self.calls += 1
        return [SimpleNamespace(id="t1", default_columns=["Ćwiczenie", "Serie"])]


async def test_load_persona_columns_uses_template_overrides_and_missing_template() -> None:
    templates = _Templates()
    personas = [
        SimpleNamespace(id="p1", plan_template_id="t1", template_overrides=None),
        SimpleNamespace(id="p2", plan_template_id="t1", template_overrides={"columns": ["Drill", "Czas"]}),
        SimpleNamespace(id="p3", plan_template_id=None, template_overrides=None),
    ]
    columns = await load_persona_columns(templates, personas)
    assert columns == {"p1": ["Ćwiczenie", "Serie"], "p2": ["Drill", "Czas"], "p3": []}
    assert templates.calls == 1


def test_persona_out_plan_columns_defaults_to_empty() -> None:
    field = PersonaOut.model_fields["plan_columns"]
    assert field.default_factory is not None
    assert field.default_factory() == []
