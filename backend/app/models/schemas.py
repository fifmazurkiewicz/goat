"""Pydantic DTO dla API `/personas` — kolumny zgodne z docs/technical/database-schema.md.

`moderation_checked_prompt_hash` i `preamble_version` to szczegóły wewnętrzne warstwy
moderacji (security.md) — `preamble_version` jest zwracany w `PersonaOut` dla debugowania/
UI (np. baner "wymaga re-checku"), hash pozostaje wyłącznie wewnętrzny (nigdy w DTO).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PersonaType = Literal[
    "personal_trainer",
    "dietitian",
    "sport_psychologist",
    "psychologist",
    "motor_coach",
    "badminton_coach",
    "custom",
]
DetailLevel = Literal["simple", "detailed"]
ModerationStatus = Literal["pending", "approved", "rejected"]


class PersonaBase(BaseModel):
    type: PersonaType
    name: str = Field(min_length=1, max_length=100)
    # WYŁĄCZNIE sekcja edytowalna usera — platform preambuł jest doklejany server-side,
    # nigdy zapisywany tutaj (security.md sekcja 1, warstwa A).
    system_prompt: str = Field(min_length=1, max_length=4000)
    chat_model: str = "anthropic/claude-haiku-4.5"
    detail_level: DetailLevel = "simple"
    custom_result_category: str | None = None
    persona_constraints: str | None = Field(default=None, max_length=1000)
    is_shared: bool = False


class PersonaCreate(PersonaBase):
    base_template_id: str | None = None
    plan_template_id: str | None = None
    # Walidowane (schema-level, dodatkowo do przyszłej walidacji semantycznej w
    # PersonaService) PRZED zapisem — fail fast, patrz database-schema.md.
    template_overrides: dict[str, Any] | None = None


class PersonaUpdate(BaseModel):
    """Wszystkie pola opcjonalne — semantyka PATCH.

    Edycja `system_prompt` invaliduje `moderation_checked_prompt_hash` i wymaga
    recheck moderacji przed zapisem (security.md warstwa B, ADR-4) — ta logika żyje
    w `PersonaService`/`ModerationService`, nie w tym DTO.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=4000)
    chat_model: str | None = None
    detail_level: DetailLevel | None = None
    custom_result_category: str | None = None
    persona_constraints: str | None = Field(default=None, max_length=1000)
    is_shared: bool | None = None
    template_overrides: dict[str, Any] | None = None
    active: bool | None = None


class PersonaOut(PersonaBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    base_template_id: str | None = None
    plan_template_id: str | None = None
    template_overrides: dict[str, Any] | None = None
    moderation_status: ModerationStatus = "approved"
    preamble_version: int = 1
    cloned_from_persona_id: str | None = None
    active: bool = True
    created_at: datetime
    updated_at: datetime


# ============ Profil użytkownika (biometria) — patrz database-schema.md, ai-pipeline.md §0, ADR-11 ============

Sex = Literal["male", "female", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
PrimaryGoal = Literal[
    "lose_weight", "build_muscle", "improve_endurance", "general_health", "sport_specific"
]

# Pola uznane za "krytyczne" dla personalizacji — używane przez ContextBuilder do
# wykrycia niekompletności profilu i doklejenia instrukcji "dopytaj o brakujące dane"
# (ai-pipeline.md §0). `notes` i `sex` celowo NIE są krytyczne (opcjonalny kontekst).
CRITICAL_PROFILE_FIELDS: tuple[str, ...] = (
    "height_cm",
    "weight_kg",
    "date_of_birth",
    "activity_level",
    "primary_goal",
)


class UserProfileUpdate(BaseModel):
    """Argumenty narzędzia `update_user_profile` ORAZ ciało `PATCH /api/v1/profile`
    (ten sam kształt — obie ścieżki, konwersacyjna i formularz, piszą to samo).

    Wszystkie pola opcjonalne — częściowa aktualizacja, tylko podane pola są nadpisywane.
    Walidacja zakresów zgodna z CHECK constraints w `supabase/migrations/0002_user_profile.sql`
    — zduplikowana świadomie po stronie Pydantic, żeby błąd wracał do modelu jako czytelny
    tool response PRZED uderzeniem w bazę (ai-pipeline.md §0), nie jako surowy błąd SQL.
    """

    height_cm: float | None = Field(default=None, ge=100, le=250)
    weight_kg: float | None = Field(default=None, ge=20, le=400)
    date_of_birth: date | None = None
    sex: Sex | None = None
    activity_level: ActivityLevel | None = None
    primary_goal: PrimaryGoal | None = None
    notes: str | None = Field(default=None, max_length=1000)


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    height_cm: float | None = None
    weight_kg: float | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    activity_level: ActivityLevel | None = None
    primary_goal: PrimaryGoal | None = None
    notes: str | None = None
    updated_at: datetime

    @property
    def missing_critical_fields(self) -> list[str]:
        """Używane przez `ContextBuilder` (ai-pipeline.md §0) do zbudowania instrukcji
        "dopytaj o brakujące dane" — znika automatycznie z promptu, gdy lista jest pusta."""
        return [field for field in CRITICAL_PROFILE_FIELDS if getattr(self, field) is None]


# ============ Admin — limit person per konto (ADR-12) ============


class PersonaLimitUpdate(BaseModel):
    """Ciało `PATCH /api/v1/admin/users/{user_id}/persona-limit`.

    Zakres 0-50 zgodny z `CHECK` w `supabase/migrations/0003_persona_limit_per_account.sql`
    — walidacja tutaj jest szybszym, czytelniejszym feedbackiem dla admina, NIE jedyną
    barierą (baza pozostaje ostateczną linią obrony, tak jak przy `log_result`)."""

    max_active_personas: int = Field(ge=0, le=50)


class AdminUserOut(BaseModel):
    """`GET /api/v1/admin/users` — widok admina na konto usera (nie mylić z `PersonaOut`)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    is_admin: bool
    max_active_personas: int
    created_at: datetime
