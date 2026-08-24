"""Task 4 — general turn routing: Goat vs slash (GWT-1 / GWT-5)."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.chat.orchestrator import should_run_goat_turn


@dataclass
class _FakePersona:
    id: str
    type: str
    slug: str
    name: str = "Trener"
    system_prompt: str = "Jestem trenerem."


def test_should_run_goat_turn_without_slash() -> None:
    personas = [_FakePersona(id="a", type="dietitian", slug="dietetyk")]
    assert should_run_goat_turn("Jak poprawić plyometrię?", personas) is True
    assert should_run_goat_turn("/dietetyk co jeść", personas) is False


def test_should_run_goat_turn_false_for_multi_slash() -> None:
    personas = [
        _FakePersona(id="a", type="dietitian", slug="dietetyk"),
        _FakePersona(id="b", type="motor_coach", slug="motoryka"),
    ]
    assert should_run_goat_turn("/dietetyk /motoryka ułóż plan", personas) is False


def test_should_run_goat_turn_true_when_slash_not_matched() -> None:
    personas = [_FakePersona(id="a", type="dietitian", slug="dietetyk")]
    assert should_run_goat_turn("/motoryka plyometria", personas) is True
    assert should_run_goat_turn("/dietetyk", personas) is True