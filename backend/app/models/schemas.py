"""Pydantic DTOs for the `/personas` API — columns per docs/technical/database-schema.md.

`moderation_checked_prompt_hash` and `preamble_version` are internal moderation layer
details (security.md) — `preamble_version` is returned in `PersonaOut` for
debugging/UI (e.g. "requires re-check" banner), the hash stays internal only (never in DTO).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

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
    """Shape of `personas.template_overrides` — `{"columns":[...]}` (database-schema.md)."""

    columns: list[str] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def _nonempty_unique_columns(self) -> TemplateOverrides:
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
    # ONLY the user-editable section — the platform preamble is appended server-side,
    # never stored here (security.md section 1, layer A).
    system_prompt: str = Field(min_length=1, max_length=4000)
    detail_level: DetailLevel = "simple"
    custom_result_category: str | None = None
    is_shared: bool = False
    # `persona_constraints` is INTENTIONALLY NOT in the API DTO — a system / operator
    # field (ai-pipeline.md); it lives in DB and is only read server-side (chat/plan).


class PersonaCreate(PersonaBase):
    base_template_id: str | None = None
    plan_template_id: str | None = None
    # Validated (schema-level, in addition to future semantic validation in
    # PersonaService) BEFORE write — fail fast, see database-schema.md.
    template_overrides: TemplateOverrides | None = None

    @model_validator(mode="after")
    def _custom_requires_category(self) -> PersonaCreate:
        if self.type == "custom" and not self.custom_result_category:
            raise ValueError("custom_result_category jest wymagane dla type='custom'.")
        return self


class PersonaUpdate(BaseModel):
    """All fields optional — PATCH semantics.

    Editing `system_prompt` invalidates `moderation_checked_prompt_hash` and requires
    a moderation re-check before writing (security.md layer B, ADR-4) — that logic
    lives in `PersonaService`/`ModerationService`, not in this DTO.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=4000)
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
    """`GET /api/v1/personas` — list + active limit from `profiles` (ADR-12)."""

    items: list[PersonaOut]
    max_active_personas: int


class PersonaTemplateOut(BaseModel):
    """`GET /api/v1/persona-templates` — persona templates (read-only seed)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: PersonaType
    default_prompt: str
    label: str
    created_at: datetime


class PlanTemplateOut(BaseModel):
    """`GET /api/v1/plan-templates` — day structure templates (read-only seed)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    suggested_for: list[str]
    default_columns: list[str]
    default_rows: list[Any] = Field(default_factory=list)
    created_at: datetime


# ============ User profile (biometrics) — see database-schema.md, ai-pipeline.md §0, ADR-11 ============

Sex = Literal["male", "female", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
PrimaryGoal = Literal["lose_weight", "build_muscle", "improve_endurance", "general_health", "sport_specific"]

# Fields considered "critical" for personalization — used by ContextBuilder to detect
# incomplete profile and append the "ask about missing data" instruction
# (ai-pipeline.md §0). `notes` and `sex` are intentionally NOT critical (optional context).
CRITICAL_PROFILE_FIELDS: tuple[str, ...] = (
    "height_cm",
    "weight_kg",
    "date_of_birth",
    "activity_level",
    "primary_goal",
)


class UserProfileUpdate(BaseModel):
    """Arguments for the `update_user_profile` tool AND body of `PATCH /api/v1/profile`
    (same shape — both paths, conversational and form, write the same thing).

    All fields optional — partial update, only the given fields are overwritten.
    Range validation matches the CHECK constraints in
    `supabase/migrations/0002_user_profile.sql` — intentionally duplicated on the
    Pydantic side so the error returns to the model as a readable tool response
    BEFORE hitting the DB (ai-pipeline.md §0), not as a raw SQL error.
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
        """Used by `ContextBuilder` (ai-pipeline.md §0) to build the
        "ask about missing data" instruction — disappears automatically from the
        prompt when the list is empty."""
        return [field for field in CRITICAL_PROFILE_FIELDS if getattr(self, field) is None]


# ============ Admin — personas limit per account (ADR-12) ============


class DeployInfoOut(BaseModel):
    """`GET /api/v1/admin/deploy-info` — app semver + deploy commit metadata."""

    component: Literal["api"] = "api"
    app_version: str
    environment: str
    git_sha: str | None = None
    git_sha_full: str | None = None
    git_branch: str | None = None
    build_time: str | None = None
    git_repo: str = "fifmazurkiewicz/goat"


class PersonaLimitUpdate(BaseModel):
    """Body of `PATCH /api/v1/admin/users/{user_id}/persona-limit`.

    Range 0-50 per `CHECK` in `supabase/migrations/0003_persona_limit_per_account.sql`
    — validation here is faster, more readable feedback for the admin, NOT the only
    barrier (the DB remains the last line of defense, just like `log_result`)."""

    max_active_personas: int = Field(ge=0, le=50)


class AdminUserOut(BaseModel):
    """`GET /api/v1/admin/users` — admin view of a user account (don't confuse with `PersonaOut`).

    `cost_usd_used`/`usage_budget_usd` shown DIRECTLY as an amount, WITHOUT "Free"/"Pro"
    labels (ADR-16) — `email` from `auth.users` (Postgres; Auth Admin API fills gaps),
    not from `profiles`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None = None
    is_admin: bool
    is_approved: bool
    max_active_personas: int
    usage_budget_usd: float
    cost_usd_used: float = 0.0
    created_at: datetime


class UsageBudgetUpdate(BaseModel):
    """Body of `PATCH /api/v1/admin/users/{user_id}/usage-budget` (ADR-16) — same
    pattern as `PersonaLimitUpdate`."""

    usage_budget_usd: float = Field(ge=0, le=1000)


class ApprovalUpdate(BaseModel):
    """Body of `PATCH /api/v1/admin/users/{user_id}/approval` (ADR-22)."""

    is_approved: bool


class PasswordResetOut(BaseModel):
    """`POST /api/v1/admin/users/{user_id}/reset-password` — temporary password for
    ONE-TIME display to the admin (never logged/persisted beyond this response),
    see `app/core/supabase_admin.py`."""

    temporary_password: str


class AuditLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    admin_user_id: str
    action: str
    target_user_id: str | None = None
    details: dict[str, Any] | None = None
    created_at: datetime


# ============ Auth (local dev) ============


class DevLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


# ============ Account — nick (ADR-15, separate from /profile — biometrics) ============


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nick: str | None = None
    is_admin: bool = False
    is_approved: bool = False


class AccountUpdate(BaseModel):
    nick: str | None = Field(default=None, max_length=100)


# ============ Usage (ADR-16) ============


class UsageLimitsOut(BaseModel):
    """`GET /api/v1/usage` — budget + current period consumption (90% badge on FE)."""

    user_id: str
    period_start: date
    period_renews_at: date
    messages_used: int = 0
    tokens_used: int = 0
    plan_generations_used: int = 0
    cost_usd_used: float = 0.0
    usage_budget_usd: float


# ============ Exercise catalog (ADR-14) ============

ExerciseLevel = Literal["beginner", "intermediate", "advanced"]


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    name_en: str | None = None
    persona_type: PersonaType
    level: ExerciseLevel
    categories: list[str]
    short_description: str
    detail_full: str
    common_mistakes: str | None = None
    photo_path: str | None = None
    photo_path_2: str | None = None


# ============ Results (`/results`, database-schema.md, ADR-9) ============

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


# ============ `log_result` tool — LLM argument validation (ai-pipeline.md §2, ADR-6) ============
# Untrusted input even though it comes from "our" model (security.md §3) — Pydantic
# validation BEFORE any write, separately per entry (partial batch success).


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
InvokedVia = Literal["auto_routed", "slash_command", "multi_slash"]


class ChatSessionCreate(BaseModel):
    """`persona_id=None` -> `general` session (auto-routing, ADR-13); given -> `persona`
    session (1:1, no change from the original behavior)."""

    persona_id: str | None = None
    title: str | None = Field(default=None, max_length=200)


class ChatSessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ChatSessionTurnStatus(BaseModel):
    in_progress: bool


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    persona_id: str | None = None
    session_type: ChatSessionType
    title: str | None = None
    turn_in_progress: bool = False
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: ChatRole
    content: str | None = None
    # Consultation visibility (2026-08-22): the FE pairs `role='tool'` with
    # `consult_persona` invocations in the preceding Goat message by tool_call_id.
    tool_calls: dict[str, Any] | list[dict[str, Any]] | None = None
    persona_id: str | None = None
    invoked_via: InvokedVia | None = None
    created_at: datetime


class ChatSendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    # Retry after broken SSE — don't insert the same user message twice
    # (frontend.md: "Send again" = new request, user history is already in DB).
    retry: bool = False


# ============ Plans (`/plans`, architecture.md §4, ADR-1/2) ============

PlanPeriodType = Literal["week", "month"]
PlanStatus = Literal["generating", "ready", "partial_ready", "error"]
JobStatus = Literal["pending", "running", "success", "partial_success", "error"]
JobPersonaStatus = Literal["pending", "running", "done", "failed"]


class PlanGenerateRequest(BaseModel):
    period_type: PlanPeriodType
    start_date: date


class PlanItemContent(BaseModel):
    """Shape of `plan_items.content` (jsonb) — a FROZEN snapshot at generation time,
    never a live ref to `plan_templates`/`personas.template_overrides`."""

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


class PlanSummaryOut(BaseModel):
    """Plan metadata without `items` — contract for `GET /plans?start_date=&end_date=`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    period_type: PlanPeriodType
    start_date: date
    end_date: date
    status: PlanStatus
    created_at: datetime
    updated_at: datetime


class PlanRangeOut(BaseModel):
    plan: PlanSummaryOut | None = None
    items: list[PlanItemOut] = Field(default_factory=list)


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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def job_id(self) -> str:
        """Alias for the frontend (historical contract used `job_id` instead of `id`)."""
        return self.id
