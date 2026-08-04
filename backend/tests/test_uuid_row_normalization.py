"""UUID/Decimal normalization for ProfileRow / PersonaRow (asyncpg → DTO)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.repositories.personas_repo import _row_to_persona
from app.repositories.profiles_repo import _row_to_profile


class _MappingRow:
    def __init__(self, mapping: dict) -> None:
        self._mapping = mapping


def test_profile_row_stringifies_uuid_and_decimal() -> None:
    profile_id = uuid4()
    row = _MappingRow(
        {
            "id": profile_id,
            "is_admin": False,
            "max_active_personas": 5,
            "nick": "Admin",
            "usage_budget_usd": Decimal("10.00"),
            "created_at": datetime.now(timezone.utc),
        }
    )
    profile = _row_to_profile(row)
    assert profile.id == str(profile_id)
    assert isinstance(profile.usage_budget_usd, float)
    assert profile.usage_budget_usd == 10.0


def test_persona_row_stringifies_uuid_fks() -> None:
    persona_id = uuid4()
    user_id = uuid4()
    template_id = uuid4()
    row = _MappingRow(
        {
            "id": persona_id,
            "user_id": user_id,
            "type": "dietitian",
            "name": "Dietetyk",
            "system_prompt": "prompt",
            "base_template_id": template_id,
            "chat_model": "anthropic/claude-haiku-4.5",
            "plan_template_id": None,
            "template_overrides": {"columns": ["Kolumna 1"]},
            "detail_level": "simple",
            "custom_result_category": None,
            "persona_constraints": None,
            "slug": "dietitian_dietetyk",
            "is_shared": False,
            "moderation_status": "approved",
            "moderation_checked_prompt_hash": "abc",
            "preamble_version": 2,
            "cloned_from_persona_id": None,
            "active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    persona = _row_to_persona(row)
    assert persona.id == str(persona_id)
    assert persona.user_id == str(user_id)
    assert persona.base_template_id == str(template_id)
