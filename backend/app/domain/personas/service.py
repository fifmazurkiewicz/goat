"""`PersonaService` — logika biznesowa person (limit aktywnych, merge kolumn planu).

Router `/personas` (api/routers/personas.py) ma pozostać cienki i wywoływać wyłącznie
metody tej klasy — cała reguła biznesowa żyje tutaj (architecture.md sekcja 1).
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.exceptions import PersonaLimitExceededError
from app.repositories.profiles_repo import DEFAULT_MAX_ACTIVE_PERSONAS


class PersonasRepositoryProtocol(Protocol):
    async def list_for_user(self, user_id: str) -> list[Any]: ...
    async def count_active(self, user_id: str) -> int: ...


class ProfilesRepositoryProtocol(Protocol):
    async def get(self, user_id: str) -> Any: ...


class PersonaService:
    """Nie zna FastAPI/HTTP — testowalna bezpośrednio z fake repo (architecture.md #7).

    Limit aktywnych person jest PER KONTO (`profiles.max_active_personas`, ADR-12) —
    NIE globalna stała w kodzie. `ProfilesRepo` dodany jako zależność, żeby serwis mógł
    odczytać limit konkretnego usera przed porównaniem z `count_active`.
    """

    def __init__(
        self,
        personas_repo: PersonasRepositoryProtocol,
        profiles_repo: ProfilesRepositoryProtocol,
    ) -> None:
        self._personas_repo = personas_repo
        self._profiles_repo = profiles_repo

    async def assert_can_activate_persona(self, user_id: str) -> None:
        """Sprawdza `count_active(user_id) < profiles.max_active_personas` (fallback
        `DEFAULT_MAX_ACTIVE_PERSONAS` gdy profil z jakiegoś powodu nie istnieje — nie
        powinno się zdarzyć poza testami, `handle_new_user` trigger tworzy wiersz
        `profiles` przy rejestracji), inaczej rzuca `PersonaLimitExceededError` (409).

        Trigger DB `enforce_persona_limit` (supabase/migrations/0003_...sql) pozostaje
        ostateczną linią obrony — ten check tu daje tylko czytelny komunikat przed
        uderzeniem w bazę (ten sam wzorzec co pierwotny limit "5", patrz ADR-12).
        """
        profile = await self._profiles_repo.get(user_id)
        max_allowed = profile.max_active_personas if profile else DEFAULT_MAX_ACTIVE_PERSONAS

        active_count = await self._personas_repo.count_active(user_id)
        if active_count >= max_allowed:
            raise PersonaLimitExceededError(
                f"Osiągnięto limit aktywnych person ({max_allowed}). Poproś administratora "
                "o zwiększenie limitu albo dezaktywuj inną personę."
            )


def resolve_persona_columns(
    persona: dict[str, Any], plan_template: dict[str, Any]
) -> dict[str, Any]:
    """Merguje kolumny persony z jej bazowym `plan_template`.

    Kontrakt (docs/technical/database-schema.md): `plan_templates.default_columns`
    to bazowa lista kolumn (np. `["Ćwiczenie","Serie","Powtórzenia","Ciężar","Uwagi"]`),
    a `personas.template_overrides` (walidowane Pydantic PRZED zapisem, fail fast —
    nie late failure w trakcie generowania planu) może nadpisywać/rozszerzać podzbiór
    tych kolumn per-persona.

    TODO pełna implementacja: deterministyczny merge `default_columns` +
    `template_overrides` (override wygrywa per klucz, brak duplikatów kolumn,
    zachowanie kolejności bazowej dla kolumn niezmienionych) — patrz
    docs/technical/architecture.md i docs/technical/database-schema.md (sekcje
    `plan_templates`/`personas`).
    """
    raise NotImplementedError(
        "resolve_persona_columns — do zaimplementowania w etapie personas, patrz "
        "docs/technical/database-schema.md (plan_templates.default_columns / "
        "personas.template_overrides)."
    )
