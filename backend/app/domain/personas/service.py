"""`PersonaService` — logika biznesowa person (CRUD, limit aktywnych, slug, moderacja,
community, klonowanie, merge kolumn planu).

Router `/personas` (api/routers/personas.py) ma pozostać cienki i wywoływać wyłącznie
metody tej klasy — cała reguła biznesowa żyje tutaj (architecture.md sekcja 1).
"""

from __future__ import annotations

import re
from typing import Any, Literal, Protocol

from app.core.exceptions import ModerationRejectedError, NotFoundError, PersonaLimitExceededError
from app.repositories.profiles_repo import DEFAULT_MAX_ACTIVE_PERSONAS

# ============ Protocols (DI — architecture.md sekcja 7) ============


class PersonasRepositoryProtocol(Protocol):
    async def list_for_user(self, user_id: str) -> list[Any]: ...
    async def list_community(self, *, exclude_user_id: str) -> list[Any]: ...
    async def get_visible(self, persona_id: str) -> Any | None: ...
    async def get_own(self, persona_id: str, user_id: str) -> Any | None: ...
    async def list_slugs_for_user(self, user_id: str) -> set[str]: ...
    async def count_active(self, user_id: str) -> int: ...
    async def create(self, user_id: str, values: dict[str, Any]) -> Any: ...
    async def update(self, persona_id: str, user_id: str, values: dict[str, Any]) -> Any: ...
    async def delete(self, persona_id: str, user_id: str) -> None: ...


class ProfilesRepositoryProtocol(Protocol):
    async def get(self, user_id: str) -> Any: ...


class ModerationServiceProtocol(Protocol):
    async def check_persona_prompt(
        self,
        *,
        user_id: str,
        persona_id: str | None,
        user_prompt: str,
        trigger_type: Literal["persona_create", "persona_edit", "persona_share"],
        previous_hash: str | None = None,
        previous_status: str | None = None,
        previous_preamble_version: int | None = None,
    ) -> Any: ...


# ============ Slug generation (ADR-13) ============

_SLUG_SANITIZE_RE = re.compile(r"[^a-z0-9]+")


def generate_base_slug(persona_type: str, name: str) -> str:
    """`slug` generowany z `type + name` (ADR-13), sanitized do `^[a-z0-9_]+$`
    (zgodnie z CHECK constraint w `0004_general_chat_and_persona_slug.sql`)."""
    raw = f"{persona_type}_{name}".lower()
    slug = _SLUG_SANITIZE_RE.sub("_", raw).strip("_")
    return slug or "persona"


def resolve_slug_collision(base_slug: str, existing_slugs: set[str]) -> str:
    """Kolizje rozwiązywane numerycznym suffixem (`_2`, `_3`, ...) — unikalność
    per user, nie globalnie (ADR-13)."""
    if base_slug not in existing_slugs:
        return base_slug
    suffix = 2
    while f"{base_slug}_{suffix}" in existing_slugs:
        suffix += 1
    return f"{base_slug}_{suffix}"


class PersonaService:
    """Nie zna FastAPI/HTTP — testowalna bezpośrednio z fake repo (architecture.md #7).

    Limit aktywnych person jest PER KONTO (`profiles.max_active_personas`, ADR-12) —
    NIE globalna stała w kodzie.
    """

    def __init__(
        self,
        personas_repo: PersonasRepositoryProtocol,
        profiles_repo: ProfilesRepositoryProtocol,
        moderation_service: ModerationServiceProtocol,
    ) -> None:
        self._personas_repo = personas_repo
        self._profiles_repo = profiles_repo
        self._moderation_service = moderation_service

    async def assert_can_activate_persona(self, user_id: str) -> None:
        """Sprawdza `count_active(user_id) < profiles.max_active_personas` (fallback
        `DEFAULT_MAX_ACTIVE_PERSONAS` gdy profil nie istnieje), inaczej rzuca
        `PersonaLimitExceededError` (409).

        Trigger DB `enforce_persona_limit` pozostaje ostateczną linią obrony — ten
        check tu daje tylko czytelny komunikat przed uderzeniem w bazę (ADR-12).
        """
        profile = await self._profiles_repo.get(user_id)
        max_allowed = profile.max_active_personas if profile else DEFAULT_MAX_ACTIVE_PERSONAS

        active_count = await self._personas_repo.count_active(user_id)
        if active_count >= max_allowed:
            raise PersonaLimitExceededError(
                f"Osiągnięto limit aktywnych person ({max_allowed}). Poproś administratora "
                "o zwiększenie limitu albo dezaktywuj inną personę."
            )

    async def list_own(self, user_id: str) -> list[Any]:
        return await self._personas_repo.list_for_user(user_id)

    async def list_community(self, user_id: str) -> list[Any]:
        return await self._personas_repo.list_community(exclude_user_id=user_id)

    async def get_persona(self, persona_id: str, user_id: str) -> Any:
        persona = await self._personas_repo.get_visible(persona_id)
        if persona is None:
            raise NotFoundError(f"Persona {persona_id!r} nie istnieje.")
        return persona

    async def create_persona(self, user_id: str, payload: dict[str, Any]) -> Any:
        """`payload` — pola z `PersonaCreate.model_dump()` (router). Persona jest
        aktywna domyślnie (`active=true`), więc limit jest sprawdzany na KAŻDYM create."""
        await self.assert_can_activate_persona(user_id)

        # `persona_constraints` nigdy z klienta (ai-pipeline.md — pole systemowe).
        safe_payload = {k: v for k, v in payload.items() if k != "persona_constraints"}

        persona_type = safe_payload["type"]
        name = safe_payload["name"]
        base_slug = generate_base_slug(persona_type, name)
        existing_slugs = await self._personas_repo.list_slugs_for_user(user_id)
        slug = resolve_slug_collision(base_slug, existing_slugs)

        moderation = await self._moderation_service.check_persona_prompt(
            user_id=user_id,
            persona_id=None,
            user_prompt=safe_payload["system_prompt"],
            trigger_type="persona_create",
        )
        if moderation.status == "rejected":
            raise ModerationRejectedError(
                "Opis persony nie przeszedł moderacji — treść wykracza poza zakres "
                "coachingu sportowego/dietetycznego/psychologicznego albo próbuje "
                "zmienić rolę modelu."
            )

        values = {
            **safe_payload,
            "slug": slug,
            "moderation_status": moderation.status,
            "moderation_checked_prompt_hash": moderation.checked_prompt_hash,
            "preamble_version": moderation.preamble_version,
        }
        return await self._personas_repo.create(user_id, values)

    async def update_persona(
        self, persona_id: str, user_id: str, updates: dict[str, Any]
    ) -> Any:
        """`updates` — `PersonaUpdate.model_dump(exclude_unset=True)` (router), tylko
        pola faktycznie podane w PATCH."""
        existing = await self._personas_repo.get_own(persona_id, user_id)
        if existing is None:
            raise NotFoundError(f"Persona {persona_id!r} nie istnieje lub nie należy do usera.")

        # End-user nie może nadpisać ograniczeń medycznych/systemowych.
        values: dict[str, Any] = {
            k: v for k, v in updates.items() if k != "persona_constraints"
        }

        if "name" in updates and updates["name"] != existing.name:
            base_slug = generate_base_slug(existing.type, updates["name"])
            existing_slugs = await self._personas_repo.list_slugs_for_user(user_id)
            existing_slugs.discard(existing.slug)
            values["slug"] = resolve_slug_collision(base_slug, existing_slugs)

        wants_share = updates.get("is_shared") is True and not existing.is_shared
        prompt_changed = "system_prompt" in updates and updates["system_prompt"] != existing.system_prompt

        if prompt_changed or wants_share:
            prompt_to_check = updates.get("system_prompt", existing.system_prompt)
            trigger: Literal["persona_edit", "persona_share"] = (
                "persona_share" if wants_share and not prompt_changed else "persona_edit"
            )
            moderation = await self._moderation_service.check_persona_prompt(
                user_id=user_id,
                persona_id=persona_id,
                user_prompt=prompt_to_check,
                trigger_type=trigger,
                previous_hash=existing.moderation_checked_prompt_hash,
                previous_status=existing.moderation_status,
                previous_preamble_version=existing.preamble_version,
            )
            if moderation.status == "rejected":
                raise ModerationRejectedError(
                    "Zmieniona treść persony nie przeszła moderacji — treść wykracza poza "
                    "zakres coachingu albo próbuje zmienić rolę modelu."
                )
            values["moderation_status"] = moderation.status
            values["moderation_checked_prompt_hash"] = moderation.checked_prompt_hash
            values["preamble_version"] = moderation.preamble_version

        wants_activate = updates.get("active") is True and not existing.active
        if wants_activate:
            await self.assert_can_activate_persona(user_id)

        return await self._personas_repo.update(persona_id, user_id, values)

    async def delete_persona(self, persona_id: str, user_id: str) -> None:
        await self._personas_repo.delete(persona_id, user_id)

    async def share_persona(self, persona_id: str, user_id: str, is_shared: bool) -> Any:
        """`PATCH /personas/{id}/share` — semantycznie subset `update_persona`, ale
        osobny endpoint w spec (czytelniejszy kontrakt API dla akcji "udostępnij")."""
        return await self.update_persona(persona_id, user_id, {"is_shared": is_shared})

    async def clone_persona(self, persona_id: str, user_id: str) -> Any:
        """Klonowanie z community — NOWY rekord z `user_id=auth.uid()`, nigdy nie
        modyfikuje oryginału (database-schema.md, sekcja RLS). Treść była już
        zmoderowana jako `is_shared+approved` u źródła — kopiujemy werdykt zamiast
        re-klasyfikować identyczną treść."""
        await self.assert_can_activate_persona(user_id)

        source = await self._personas_repo.get_visible(persona_id)
        if source is None:
            raise NotFoundError(f"Persona {persona_id!r} nie istnieje.")

        base_slug = generate_base_slug(source.type, source.name)
        existing_slugs = await self._personas_repo.list_slugs_for_user(user_id)
        slug = resolve_slug_collision(base_slug, existing_slugs)

        values = {
            "type": source.type,
            "name": source.name,
            "system_prompt": source.system_prompt,
            "base_template_id": source.base_template_id,
            "chat_model": source.chat_model,
            "plan_template_id": source.plan_template_id,
            "template_overrides": source.template_overrides,
            "detail_level": source.detail_level,
            "custom_result_category": source.custom_result_category,
            # Constraints są operatorskie per-konto — nie kopiujemy z community.
            "persona_constraints": None,
            "is_shared": False,
            "slug": slug,
            "moderation_status": source.moderation_status,
            "moderation_checked_prompt_hash": source.moderation_checked_prompt_hash,
            "preamble_version": source.preamble_version,
            "cloned_from_persona_id": source.id,
        }
        return await self._personas_repo.create(user_id, values)


def resolve_persona_columns(
    persona: dict[str, Any], plan_template: dict[str, Any] | None
) -> list[str]:
    """Merguje kolumny persony z jej bazowym `plan_template`.

    Kontrakt (docs/technical/database-schema.md): `plan_templates.default_columns`
    to baza; `personas.template_overrides` ma kształt `{"columns": list[str]}` —
    pełna lista kolumn z edytora (nie diff). Brak klucza `columns` / `None` →
    `default_columns`. Deduplikacja chroni przed uszkodzonymi danymi w DB.
    """
    default_columns: list[str] = list((plan_template or {}).get("default_columns") or [])
    overrides = persona.get("template_overrides") or {}
    override_columns = overrides.get("columns")

    if override_columns is None:
        return default_columns

    seen: set[str] = set()
    result: list[str] = []
    for column in override_columns:
        if column not in seen:
            seen.add(column)
            result.append(column)
    return result
