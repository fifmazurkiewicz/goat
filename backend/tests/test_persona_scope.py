"""Testy mapowania zakresu ról person."""

from __future__ import annotations

from app.domain.chat.persona_scope import (
    PERSONA_OUT_OF_SCOPE,
    PERSONA_TYPE_SCOPE,
    build_persona_scope_block,
    routing_persona_line,
)


def test_all_builtin_persona_types_have_scope_and_boundaries() -> None:
    expected = {
        "personal_trainer",
        "dietitian",
        "sport_psychologist",
        "psychologist",
        "motor_coach",
        "badminton_coach",
        "team_lead",
        "custom",
    }
    assert set(PERSONA_TYPE_SCOPE) == expected
    assert set(PERSONA_OUT_OF_SCOPE) == expected


def test_scope_block_requires_staying_in_role() -> None:
    block = build_persona_scope_block("dietitian")
    assert "[ZAKRES ROLI" in block
    assert "Nie wypowiadasz się za inne persony" in block
    assert "Twój zakres:" in block
    assert "Poza zakresem" in block


def test_scope_block_for_trainer_redirects_diet_and_motor() -> None:
    block = build_persona_scope_block("personal_trainer")
    assert "dietetyk" in block.lower()
    assert "trener motoryczny" in block.lower()


def test_scope_block_for_team_lead_redirects_to_trainers() -> None:
    block = build_persona_scope_block("team_lead")
    assert "Goat" in block or "kierownik" in block.lower() or "trener" in block.lower()
    assert "Nie wypowiadasz się za inne persony" in block


def test_routing_persona_line_includes_scope() -> None:
    line = routing_persona_line(
        persona_id="p1",
        persona_type="motor_coach",
        first_sentence="Jesteś trenerem motorycznym.",
    )
    assert "id=p1" in line
    assert "zakres:" in line
    assert "plyometria" in line
