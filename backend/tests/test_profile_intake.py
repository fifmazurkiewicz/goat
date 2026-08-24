"""Tests for `build_profile_intake_instruction` — the only non-trivial logic (not a skeleton
just reporting `NotImplementedError`) added in the user-profile stage (ADR-11,
docs/technical/ai-pipeline.md section 0)."""

from __future__ import annotations

from datetime import date, datetime

from app.domain.chat.tools import build_profile_intake_instruction
from app.models.schemas import UserProfileOut


def _profile(**overrides: object) -> UserProfileOut:
    defaults: dict[str, object] = {
        "user_id": "u1",
        "height_cm": 180.0,
        "weight_kg": 80.0,
        "date_of_birth": date(1990, 1, 1),
        "sex": "male",
        "activity_level": "moderate",
        "primary_goal": "build_muscle",
        "notes": None,
        "updated_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    return UserProfileOut(**defaults)  # type: ignore[arg-type]


def test_no_profile_yields_full_intake_instruction() -> None:
    instruction = build_profile_intake_instruction(None)

    assert instruction is not None
    assert "wzrost" in instruction
    assert "waga" in instruction
    assert "update_user_profile" in instruction


def test_complete_profile_yields_no_instruction() -> None:
    assert build_profile_intake_instruction(_profile()) is None


def test_partial_profile_lists_only_missing_fields() -> None:
    instruction = build_profile_intake_instruction(
        _profile(weight_kg=None, activity_level=None)
    )

    assert instruction is not None
    assert "waga" in instruction
    assert "poziom aktywności" in instruction
    assert "wzrost" not in instruction
    assert "główny cel" not in instruction