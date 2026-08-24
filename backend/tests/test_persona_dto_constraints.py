"""PersonaCreate/Update — shape of template_overrides and absence of persona_constraints in DTO."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.schemas import PersonaCreate, PersonaOut, PersonaUpdate, TemplateOverrides


def test_template_overrides_accepts_columns_dict() -> None:
    payload = PersonaCreate(
        type="dietitian",
        name="Dietetyk",
        system_prompt="Jesteś dietetykiem sportowym z naciskiem na regenerację.",
        template_overrides=TemplateOverrides(columns=["Posiłek", "Kcal"]),
    )
    dumped = payload.model_dump()
    assert dumped["template_overrides"] == {"columns": ["Posiłek", "Kcal"]}


def test_template_overrides_rejects_empty_columns() -> None:
    with pytest.raises(ValidationError):
        TemplateOverrides(columns=[])


def test_template_overrides_rejects_blank_or_duplicate_names() -> None:
    with pytest.raises(ValidationError):
        TemplateOverrides(columns=["A", "  "])
    with pytest.raises(ValidationError):
        TemplateOverrides(columns=["Posiłek", "posiłek"])


def test_persona_update_accepts_plan_template_id() -> None:
    update = PersonaUpdate(plan_template_id="11111111-1111-1111-1111-111111111111")
    assert update.model_dump(exclude_unset=True)["plan_template_id"].startswith("1111")


def test_persona_out_excludes_persona_constraints_even_if_present_on_source() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    class _Row:
        id = "p1"
        user_id = "u1"
        type = "personal_trainer"
        name = "Tren"
        system_prompt = "prompt wystarczająco długi"
        detail_level = "simple"
        custom_result_category = None
        is_shared = False
        base_template_id = None
        plan_template_id = None
        template_overrides = {"columns": ["A"]}
        slug = "personal_trainer_tren"
        moderation_status = "approved"
        preamble_version = 1
        cloned_from_persona_id = None
        active = True
        created_at = now
        updated_at = now
        persona_constraints = "uraz kolana — sekret"

    out = PersonaOut.model_validate(_Row())
    assert "persona_constraints" not in out.model_dump()