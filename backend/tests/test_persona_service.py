"""Testy `PersonaService.assert_can_activate_persona` — limit aktywnych person PER KONTO,
edytowalny przez admina zamiast globalnej stałej (ADR-12)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.exceptions import PersonaLimitExceededError
from app.domain.personas.service import PersonaService
from app.repositories.profiles_repo import DEFAULT_MAX_ACTIVE_PERSONAS


@dataclass
class _FakeProfile:
    max_active_personas: int


class _FakePersonasRepo:
    def __init__(self, active_count: int) -> None:
        self._active_count = active_count

    async def list_for_user(self, user_id: str) -> list[object]:
        raise NotImplementedError

    async def count_active(self, user_id: str) -> int:
        return self._active_count


class _FakeProfilesRepo:
    def __init__(self, profile: _FakeProfile | None) -> None:
        self._profile = profile

    async def get(self, user_id: str) -> _FakeProfile | None:
        return self._profile


async def test_allows_activation_below_custom_limit() -> None:
    service = PersonaService(
        personas_repo=_FakePersonasRepo(active_count=6),
        profiles_repo=_FakeProfilesRepo(_FakeProfile(max_active_personas=10)),
    )

    await service.assert_can_activate_persona("user-1")  # nie powinno rzucić


async def test_blocks_activation_at_custom_limit() -> None:
    service = PersonaService(
        personas_repo=_FakePersonasRepo(active_count=2),
        profiles_repo=_FakeProfilesRepo(_FakeProfile(max_active_personas=2)),
    )

    with pytest.raises(PersonaLimitExceededError):
        await service.assert_can_activate_persona("user-1")


async def test_falls_back_to_default_when_profile_missing() -> None:
    service = PersonaService(
        personas_repo=_FakePersonasRepo(active_count=DEFAULT_MAX_ACTIVE_PERSONAS),
        profiles_repo=_FakeProfilesRepo(None),
    )

    with pytest.raises(PersonaLimitExceededError):
        await service.assert_can_activate_persona("user-1")
