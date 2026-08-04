"""Pydantic DTO dla API `/personas` — kolumny zgodne z docs/technical/database-schema.md.

`moderation_checked_prompt_hash` i `preamble_version` to szczegóły wewnętrzne warstwy
moderacji (security.md) — `preamble_version` jest zwracany w `PersonaOut` dla debugowania/
UI (np. baner "wymaga re-checku"), hash pozostaje wyłącznie wewnętrzny (nigdy w DTO).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class TemplateOverrides(BaseModel):
    """Kształt `personas.template_overrides` — `{"columns":[...]}` (database-schema.md)."""

    columns: list[str] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def _nonempty_unique_columns(self) -> "TemplateOverrides":
        cleaned = [c.strip() for c in self.columns]
        if any(not c for c in cleaned):
            raise ValueError("Nazwy kolumn nie mogą być puste.")
        normalized = [c.casefold() for c in cleaned]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Nazwy kolumn muszą być unikalne.")
        self.columns = cleaned
        return self


class PersonaBase(BaseModel):
    type: PersonaType
    name: str = Field(min_length=1, max_length=100)
    # WYŁĄCZNIE sekcja edytowalna usera — platform preambuł jest doklejany server-side,
    # nigdy zapisywany tutaj (security.md sekcja 1, warstwa A).
    system_prompt: str = Field(min_length=1, max_length=4000)
    chat_model: str = "anthropic/claude-haiku-4.5"
    detail_level: DetailLevel = "simple"
    custom_result_category: str | None = None
    is_shared: bool = False
    # `persona_constraints` celowo NIE jest w DTO API — pole systemowe/operatorskie
    # (ai-pipeline.md); żyje w DB i jest czytane tylko server-side (chat/plan).


class PersonaCreate(PersonaBase):
    base_template_id: str | None = None
    plan_template_id: str | None = None
    # Walidowane (schema-level, dodatkowo do przyszłej walidacji semantycznej w
    # PersonaService) PRZED zapisem — fail fast, patrz database-schema.md.
    template_overrides: TemplateOverrides | None = None

    @model_validator(mode="after")
    def _custom_requires_category(self) -> "PersonaCreate":
        if self.type == "custom" and not self.custom_result_category:
            raise ValueError("custom_result_category jest wymagane dla type='custom'.")
        return self


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
    is_shared: bool | None = None
    plan_template_id: str | None = None
    template_overrides: TemplateOverrides | None = None
    active: bool | None = None


class PersonaOut(PersonaBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    base_template_id: str | None = None
    plan_template_id: str | None = None
    template_overrides: dict[str, Any] | None = None
    slug: str
    moderation_status: ModerationStatus = "approved"
    preamble_version: int = 1
    cloned_from_persona_id: str | None = None
    active: bool = True
    created_at: datetime
    updated_at: datetime


class PersonaShareUpdate(BaseModel):
    """`PATCH /api/v1/personas/{id}/share`."""

    is_shared: bool


class PersonasListOut(BaseModel):
    """`GET /api/v1/personas` — lista + limit aktywnych z `profiles` (ADR-12)."""

    items: list[PersonaOut]
    max_active_personas: int


class PersonaTemplateOut(BaseModel):
    """`GET /api/v1/persona-templates` — gotowce person (read-only seed)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: PersonaType
    default_prompt: str
    label: str
    created_at: datetime


class PlanTemplateOut(BaseModel):
    """`GET /api/v1/plan-templates` — gotowce struktury dnia (read-only seed)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    suggested_for: list[str]
    default_columns: list[str]
    default_rows: list[Any] = Field(default_factory=list)
    created_at: datetime


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
    """`GET /api/v1/admin/users` — widok admina na konto usera (nie mylić z `PersonaOut`).

    `cost_usd_used`/`usage_budget_usd` pokazywane WPROST jako kwota, BEZ etykiet
    "Free"/"Pro" (ADR-16) — `email` z `auth.users` (Supabase Admin API), nie z `profiles`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None = None
    is_admin: bool
    max_active_personas: int
    usage_budget_usd: float
    cost_usd_used: float = 0.0
    created_at: datetime


class UsageBudgetUpdate(BaseModel):
    """Ciało `PATCH /api/v1/admin/users/{user_id}/usage-budget` (ADR-16) — wzorzec
    identyczny jak `PersonaLimitUpdate`."""

    usage_budget_usd: float = Field(ge=0, le=1000)


class PasswordResetOut(BaseModel):
    """`POST /api/v1/admin/users/{user_id}/reset-password` — hasło tymczasowe do
    JEDNORAZOWEGO wyświetlenia adminowi (nigdy nie logowane/persystowane poza tym
    response), patrz `app/core/supabase_admin.py`."""

    temporary_password: str


class AuditLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    admin_user_id: str
    action: str
    target_user_id: str | None = None
    details: dict[str, Any] | None = None
    created_at: datetime


# ============ Konto — nick (ADR-15, oddzielne od /profile — biometria) ============


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nick: str | None = None
    is_admin: bool = False


class AccountUpdate(BaseModel):
    nick: str | None = Field(default=None, max_length=100)


# ============ Usage (ADR-16) ============


class UsageLimitsOut(BaseModel):
    """`GET /api/v1/usage` — budżet + zużycie bieżącego okresu (badge 90% na FE)."""

    user_id: str
    period_start: date
    period_renews_at: date
    messages_used: int = 0
    tokens_used: int = 0
    plan_generations_used: int = 0
    cost_usd_used: float = 0.0
    usage_budget_usd: float


# ============ Katalog ćwiczeń (ADR-14) ============

ExerciseLevel = Literal["beginner", "intermediate", "advanced"]


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    persona_type: PersonaType
    level: ExerciseLevel
    categories: list[str]
    short_description: str
    detail_full: str
    common_mistakes: str
    photo_path: str | None = None


# ============ Wyniki (`/results`, database-schema.md, ADR-9) ============

ResultCategory = Literal["strength", "diet", "swimming", "triathlon", "badminton", "custom"]
ResultSource = Literal["agent", "manual"]


class ResultCreate(BaseModel):
    category: ResultCategory
    metric: str = Field(min_length=1, max_length=100)
    value: float
    unit: str | None = Field(default=None, max_length=20)
    logged_date: date
    notes: str | None = Field(default=None, max_length=500)


class ResultUpdate(BaseModel):
    category: ResultCategory | None = None
    metric: str | None = Field(default=None, min_length=1, max_length=100)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=20)
    logged_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    category: ResultCategory
    metric: str
    value: float
    unit: str | None = None
    logged_date: date
    source: ResultSource
    source_persona_id: str | None = None
    is_custom: bool
    notes: str | None = None
    created_at: datetime


# ============ `log_result` tool — walidacja argumentów LLM (ai-pipeline.md §2, ADR-6) ============
# Niezaufany input mimo że pochodzi z "naszego" modelu (security.md §3) — walidacja Pydantic
# PRZED jakimkolwiek zapisem, oddzielnie per-entry (częściowy sukces batcha).


class LogResultEntry(BaseModel):
    category: ResultCategory
    metric: str = Field(min_length=1, max_length=100)
    value: float
    unit: str | None = Field(default=None, max_length=20)
    date: date
    notes: str | None = Field(default=None, max_length=500)


class LogResultArgs(BaseModel):
    entries: list[LogResultEntry] = Field(min_length=1, max_length=20)


# ============ Chat (`/chat`, architecture.md §3/§3a, ADR-13) ============

ChatSessionType = Literal["persona", "general"]
ChatRole = Literal["user", "assistant", "tool"]
InvokedVia = Literal["auto_routed", "slash_command"]


class ChatSessionCreate(BaseModel):
    """`persona_id=None` -> sesja `general` (auto-routing, ADR-13); podane -> sesja
    `persona` (1:1, bez zmian względem pierwotnego zachowania)."""

    persona_id: str | None = None
    title: str | None = Field(default=None, max_length=200)


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    persona_id: str | None = None
    session_type: ChatSessionType
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: ChatRole
    content: str | None = None
    persona_id: str | None = None
    invoked_via: InvokedVia | None = None
    created_at: datetime


class ChatSendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


# ============ Plany (`/plans`, architecture.md §4, ADR-1/2) ============

PlanPeriodType = Literal["week", "month"]
PlanStatus = Literal["generating", "ready", "partial_ready", "error"]
JobStatus = Literal["pending", "running", "success", "partial_success", "error"]
JobPersonaStatus = Literal["pending", "running", "done", "failed"]


class PlanGenerateRequest(BaseModel):
    period_type: PlanPeriodType
    start_date: date


class PlanItemContent(BaseModel):
    """Kształt `plan_items.content` (jsonb) — ZAMROŻONY snapshot w momencie generowania,
    nigdy live-ref do `plan_templates`/`personas.template_overrides`."""

    title: str
    columns: list[str]
    rows: list[dict[str, Any]]
    notes: str | None = None


class PlanItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_id: str
    item_date: date
    item_type: str
    persona_id: str
    content: dict[str, Any]
    schema_version: int


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    period_type: PlanPeriodType
    start_date: date
    end_date: date
    status: PlanStatus
    items: list[PlanItemOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PlanGenerationJobPersonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    persona_id: str
    status: JobPersonaStatus
    retry_count: int
    last_error: str | None = None


class PlanGenerationJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_id: str
    status: JobStatus
    error_message: str | None = None
    attempts: int
    personas: list[PlanGenerationJobPersonaOut] = Field(default_factory=list)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
