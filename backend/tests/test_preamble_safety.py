"""Skład system promptu: preamble + safety + zachowanie."""

from __future__ import annotations

from app.domain.chat.preamble import PREAMBLE_VERSION, build_system_prompt


def test_preamble_version_bumped_for_safety_split() -> None:
    assert PREAMBLE_VERSION >= 2


def test_build_system_prompt_orders_safety_before_behavior() -> None:
    out = build_system_prompt(
        "Styl: konkretny.",
        template_safety_prompt="Nie przepisujesz leków.",
    )
    assert "ZABEZPIECZENIA GOTOWCA" in out
    assert "Nie przepisujesz leków." in out
    assert "[ZACHOWANIE PERSONY]" in out
    assert out.index("ZABEZPIECZENIA GOTOWCA") < out.index("[ZACHOWANIE PERSONY]")
    assert "Styl: konkretny." in out


def test_build_system_prompt_orders_scope_before_behavior() -> None:
    out = build_system_prompt(
        "Styl: konkretny.",
        template_safety_prompt="Nie przepisujesz leków.",
        persona_type="dietitian",
    )
    assert out.index("[ZAKRES ROLI") < out.index("[ZACHOWANIE PERSONY]")


def test_build_system_prompt_without_safety() -> None:
    out = build_system_prompt("Tylko zachowanie.")
    assert "ZABEZPIECZENIA GOTOWCA" not in out
    assert "[ZACHOWANIE PERSONY]" in out
    assert "Tylko zachowanie." in out
