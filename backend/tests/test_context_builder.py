"""Regression test for chat context assembly (preamble → safety → behavior → constraints → profile)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.chat.context_builder import ContextBuilder, build_result_columns_block
from app.models.schemas import UserProfileOut


class _NoopChatRepo:
    async def list_recent_messages_for_context(self, **_kwargs: object) -> list[object]:
        return []


def test_context_builder_orders_segments_with_safety_and_constraints() -> None:
    builder = ContextBuilder(_NoopChatRepo(), history_window_messages=10)
    out = builder.build_system_prompt(
        persona_type="dietitian",
        persona_system_prompt="Styl: konkretny.",
        persona_constraints="Unikaj pełnych przysiadów.",
        user_profile=UserProfileOut(
            user_id="u1",
            height_cm=180,
            weight_kg=80,
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        template_safety_prompt="Nie przepisujesz leków.",
    )
    assert "ZABEZPIECZENIA GOTOWCA" in out
    assert "Nie przepisujesz leków." in out
    assert "[ZAKRES ROLI" in out
    assert "[ZACHOWANIE PERSONY]" in out
    assert "Styl: konkretny." in out
    assert "[TWARDE OGRANICZENIA PERSONY]" in out
    assert "Unikaj pełnych przysiadów." in out
    assert "[PROFIL UŻYTKOWNIKA]" in out
    assert out.index("ZABEZPIECZENIA GOTOWCA") < out.index("[ZAKRES ROLI")
    assert out.index("[ZAKRES ROLI") < out.index("[ZACHOWANIE PERSONY]")
    assert out.index("[ZACHOWANIE PERSONY]") < out.index("[TWARDE OGRANICZENIA PERSONY]")


def test_context_builder_omits_empty_optional_blocks() -> None:
    builder = ContextBuilder(_NoopChatRepo(), history_window_messages=10)
    out = builder.build_system_prompt(
        persona_type="personal_trainer",
        persona_system_prompt="Zachowanie.",
        persona_constraints=None,
        user_profile=None,
        template_safety_prompt=None,
    )
    # Preamble text names the heading; the optional safety *block* must stay off.
    assert "[ZABEZPIECZENIA GOTOWCA — NIENEDYTOWALNE" not in out
    assert "[TWARDE OGRANICZENIA PERSONY]" not in out
    assert "[PROFIL UŻYTKOWNIKA]" not in out
    assert "[ZAKRES ROLI" in out
    assert "[ZACHOWANIE PERSONY]" in out


def test_context_builder_does_not_disclose_exact_birth_date_sex_or_notes() -> None:
    builder = ContextBuilder(_NoopChatRepo(), history_window_messages=10)
    out = builder.build_system_prompt(
        persona_type="personal_trainer",
        persona_system_prompt="Zachowanie.",
        persona_constraints=None,
        user_profile=UserProfileOut(
            user_id="u1",
            date_of_birth="1990-02-03",
            sex="female",
            notes="Poufna diagnoza ABC-123",
            primary_goal="general_health",
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    )
    assert "1990-02-03" not in out
    assert "female" not in out
    assert "Poufna diagnoza" not in out
    assert "wiek:" in out
    assert "ogólne zdrowie" in out


def test_result_columns_block_for_persona_lists_its_columns() -> None:
    block = build_result_columns_block([("Bartek · Trener motoryczny", ["Ćwiczenie", "Serie"])], team_lead=False)
    assert block is not None
    assert block.startswith("[KOLUMNY WYNIKÓW]")
    assert "Ćwiczenie | Serie" in block
    assert "nie zgaduj" in block


def test_result_columns_block_for_goat_lists_each_persona() -> None:
    block = build_result_columns_block(
        [("Bartek · Trener motoryczny", ["Ćwiczenie", "Serie"]), ("Ola · Trener badmintona", ["Drill", "Czas"])],
        team_lead=True,
    )
    assert block is not None
    assert "- Bartek · Trener motoryczny: Ćwiczenie | Serie" in block
    assert "- Ola · Trener badmintona: Drill | Czas" in block


def test_result_columns_block_omitted_without_columns() -> None:
    assert build_result_columns_block([("Psycholog", [])], team_lead=False) is None
    assert build_result_columns_block([], team_lead=True) is None


def test_system_prompt_includes_result_columns_block() -> None:
    builder = ContextBuilder(_NoopChatRepo(), history_window_messages=10)
    prompt = builder.build_system_prompt(
        persona_type="motor_coach",
        persona_system_prompt="x" * 30,
        persona_constraints=None,
        user_profile=None,
        result_columns=[("Bartek", ["Ćwiczenie", "Serie"])],
    )
    assert "[KOLUMNY WYNIKÓW]" in prompt
