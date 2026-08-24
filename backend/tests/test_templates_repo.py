"""Tests for template row mapping — asyncpg returns `uuid.UUID`, the DTO requires `str`."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.schemas import PersonaTemplateOut, PlanTemplateOut
from app.repositories.templates_repo import _row_to_persona_template, _row_to_plan_template


class _FakeRow:
    def __init__(self, mapping: dict) -> None:
        self._mapping = mapping


def test_persona_template_row_serializes_uuid_id_for_api() -> None:
    template_id = uuid4()
    row = _row_to_persona_template(
        _FakeRow(
            {
                "id": template_id,
                "type": "personal_trainer",
                "default_prompt": "Prompt trenera",
                "label": "Trener personalny",
                "created_at": datetime.now(timezone.utc),
            }
        )
    )

    out = PersonaTemplateOut.model_validate(row)
    assert out.id == str(template_id)
    assert out.type == "personal_trainer"


def test_plan_template_row_serializes_uuid_id_for_api() -> None:
    template_id = uuid4()
    row = _row_to_plan_template(
        _FakeRow(
            {
                "id": template_id,
                "name": "Trening siłowy — Push/Pull/Legs",
                "suggested_for": ["personal_trainer"],
                "default_columns": '["Ćwiczenie", "Serie"]',
                "default_rows": "[]",
                "created_at": datetime.now(timezone.utc),
            }
        )
    )

    out = PlanTemplateOut.model_validate(row)
    assert out.id == str(template_id)
    assert out.default_columns == ["Ćwiczenie", "Serie"]
