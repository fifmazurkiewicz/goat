// TODO: docelowo generowane przez openapi-typescript z /openapi.json backendu
// (`npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts`)
// — patrz docs/technical/frontend.md sekcja 8.
// Na razie napisane ręcznie, zgodnie z docs/technical/database-schema.md.
// SSE eventy (ChatStreamEvent) to świadomy wyjątek — OpenAPI ich nie opisuje,
// będą definiowane ręcznie także docelowo.

export type PersonaType =
  | "personal_trainer"
  | "dietitian"
  | "sport_psychologist"
  | "psychologist"
  | "motor_coach"
  | "badminton_coach"
  | "custom";

export type DetailLevel = "simple" | "detailed";

export type ModerationStatus = "pending" | "approved" | "rejected";

export interface TemplateOverrides {
  columns: string[];
}

export interface Persona {
  id: string;
  user_id: string;
  type: PersonaType;
  name: string;
  system_prompt: string;
  base_template_id: string | null;
  plan_template_id: string | null;
  template_overrides: TemplateOverrides | null;
  detail_level: DetailLevel;
  custom_result_category: string | null;
  // ADR-13: stabilny identyfikator do "/slug wiadomość" w ogólnym czacie —
  // generowany z type+name, regenerowany przy zmianie nazwy, unikalny per user.
  slug: string;
  is_shared: boolean;
  moderation_status: ModerationStatus;
  cloned_from_persona_id: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PersonaTemplate {
  id: string;
  type: PersonaType;
  default_prompt: string;
  label: string;
  created_at: string;
}

export interface PlanTemplate {
  id: string;
  name: string;
  suggested_for: string[];
  default_columns: string[];
  default_rows: (string | number)[][] | null;
  created_at: string;
}

export interface PersonaCreateInput {
  base_template_id: string;
  type: PersonaType;
  name: string;
  system_prompt: string;
  detail_level: DetailLevel;
  plan_template_id?: string | null;
  template_overrides?: TemplateOverrides | null;
  custom_result_category?: string | null;
}

// Limit aktywnych person jest PER KONTO (profiles.max_active_personas, ADR-12) —
// odpowiedź listy person niesie go wprost, żeby UI nigdy nie hardkodował "5".
export interface PersonasListResponse {
  items: Persona[];
  max_active_personas: number;
}

export type PersonaUpdateInput = Partial<
  Pick<
    Persona,
    | "name"
    | "system_prompt"
    | "detail_level"
    | "template_overrides"
    | "custom_result_category"
    | "active"
    | "plan_template_id"
  >
>;

export type ChatRole = "user" | "assistant" | "tool";

// ADR-13: sesja 'persona' (1:1, persona_id NOT NULL) vs 'general' (auto-routing,
// persona_id NULL) — patrz docs/technical/architecture.md sekcja 3a.
export type ChatSessionType = "persona" | "general";

export interface ChatSession {
  id: string;
  user_id: string;
  persona_id: string | null;
  session_type: ChatSessionType;
  title: string | null;
  turn_in_progress?: boolean;
  created_at: string;
  updated_at: string;
}

// ADR-13: atrybucja per wiadomość — w sesji 'general' różne wiadomości assistant/tool
// mogą pochodzić od różnych person.
export type InvokedVia = "auto_routed" | "slash_command" | "multi_slash" | null;

export interface ChatMessage {
  id: string;
  session_id: string;
  role: ChatRole;
  content: string;
  tool_calls: unknown | null;
  persona_id: string | null;
  invoked_via: InvokedVia;
  created_at: string;
}

export type ResultCategory =
  | "strength"
  | "diet"
  | "swimming"
  | "triathlon"
  | "badminton"
  | "custom";

export interface Result {
  id: string;
  user_id: string;
  category: ResultCategory;
  metric: string;
  value: number;
  unit: string;
  logged_date: string;
  source: "agent" | "manual";
  source_persona_id: string | null;
  is_custom: boolean;
  notes: string | null;
  created_at: string;
}

export type PlanPeriodType = "week" | "month";
export type PlanStatus = "generating" | "ready" | "partial_ready" | "error";

export interface Plan {
  id: string;
  user_id: string;
  period_type: PlanPeriodType;
  start_date: string;
  end_date: string;
  status: PlanStatus;
  created_at: string;
  updated_at: string;
}

export interface PlanItemContent {
  title: string;
  columns: string[];
  rows: (string | number)[][];
  notes: string | null;
}

export interface PlanItem {
  id: string;
  plan_id: string;
  item_date: string;
  item_type: string;
  persona_id: string;
  content: PlanItemContent;
  schema_version: number;
  created_at: string;
}

export type PlanGenerationJobStatus =
  | "pending"
  | "running"
  | "success"
  | "partial_success"
  | "error";

export type PlanGenerationPersonaStatus = "pending" | "running" | "done" | "failed";

export interface PlanGenerationJobPersonaBreakdown {
  persona_id: string;
  status: PlanGenerationPersonaStatus;
  retry_count: number;
  last_error: string | null;
}

export interface PlanRangeResponse {
  plan: Plan | null;
  items: PlanItem[];
}

export interface GeneratePlanInput {
  period_type: PlanPeriodType;
  start_date: string;
}

export interface GeneratePlanResponse {
  plan_id: string;
  job_id: string;
}

export interface PlanGenerationJob {
  id: string;
  plan_id: string;
  status: PlanGenerationJobStatus;
  error_message: string | null;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  breakdown?: PlanGenerationJobPersonaBreakdown[];
}

// ADR-16: limit to jawny budżet w USD per konto (profiles.usage_budget_usd),
// NIE plan subskrypcyjny — kolumna `tier` usunięta z usage_limits. `usage_budget_usd`
// fizycznie żyje w `profiles` (trwały niezależnie od okresu), ale endpoint zwracający
// bieżące zużycie (`GET /api/v1/usage`) wygodnie zwraca oba razem, żeby frontend mógł
// policzyć proaktywny badge "90% budżetu" (frontend.md sekcja 10) bez dodatkowego requestu.
export interface UsageLimits {
  user_id: string;
  period_start: string;
  period_renews_at: string;
  messages_used: number;
  tokens_used: number;
  plan_generations_used: number;
  cost_usd_used: number;
  usage_budget_usd: number;
}

// Profil biometryczny — WSPÓLNY dla wszystkich person usera (odróżnij od
// systemowego `personas.persona_constraints`, niewidocznego w API dla end-usera).
// Wypełniany docelowo konwersacyjnie (tool `update_user_profile` w dowolnej rozmowie)
// — ten typ opisuje
// zarówno kształt zwracany przez `GET /profile`, jak i ciało `PATCH /profile`
// (formularz-fallback). Patrz docs/technical/ai-pipeline.md sekcja 0, ADR-11.
export type Sex = "male" | "female" | "other";
export type ActivityLevel = "sedentary" | "light" | "moderate" | "active" | "very_active";
export type PrimaryGoal =
  | "lose_weight"
  | "build_muscle"
  | "improve_endurance"
  | "general_health"
  | "sport_specific";

export interface UserProfile {
  user_id: string;
  height_cm: number | null;
  weight_kg: number | null;
  date_of_birth: string | null;
  sex: Sex | null;
  activity_level: ActivityLevel | null;
  primary_goal: PrimaryGoal | null;
  notes: string | null;
  updated_at: string;
}

export type UserProfileUpdate = Partial<Omit<UserProfile, "user_id" | "updated_at">>;

// Widok admina na konto usera — limit aktywnych person jest PER KONTO, edytowalny przez
// admina (nie globalna stała, ADR-12); kwota w USD (nie plan Free/Pro, ADR-16).
export interface AdminDeployInfo {
  component: "api";
  app_version: string;
  environment: string;
  git_sha: string | null;
  git_sha_full: string | null;
  git_branch: string | null;
  build_time: string | null;
  git_repo: string;
}

export interface AdminUser {
  id: string;
  email: string;
  nick: string | null;
  is_admin: boolean;
  max_active_personas: number;
  active_personas_count: number;
  cost_usd_used: number;
  usage_budget_usd: number;
  created_at: string;
}

export type AdminAuditAction =
  | "reset_password"
  | "edit_limits"
  | "edit_persona_limit"
  | "edit_usage_budget";

export interface AdminAuditLogEntry {
  id: string;
  admin_user_id: string;
  action: AdminAuditAction;
  target_user_id: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

export type ModerationTriggerType =
  | "persona_create"
  | "persona_edit"
  | "persona_share"
  | "chat_heuristic"
  | "chat_classifier";

export type ModerationVerdict = "clean" | "injection_attempt" | "redefine_role" | "off_topic";

export interface ModerationEvent {
  id: string;
  user_id: string;
  persona_id: string | null;
  session_id: string | null;
  message_id: string | null;
  trigger_type: ModerationTriggerType;
  raw_snippet: string;
  classifier_verdict: ModerationVerdict;
  reviewed: boolean;
  created_at: string;
}

// ADR-15: konto — nick + motyw. Motyw NIE jest tu (localStorage-only, useThemeStore) —
// ten typ opisuje wyłącznie kontrakt GET/PATCH /api/v1/account.
export interface Account {
  id: string;
  nick: string | null;
  is_admin: boolean;
  email?: string;
}

export type AccountUpdateInput = Partial<Pick<Account, "nick">>;

// ADR-14: katalog ćwiczeń, statyczna treść referencyjna seedowana migracją.
export type ExerciseLevel = "beginner" | "intermediate" | "advanced";

export interface Exercise {
  id: string;
  slug: string;
  name: string;
  persona_type: PersonaType;
  level: ExerciseLevel;
  categories: string[];
  short_description: string;
  detail_full: string;
  common_mistakes: string;
  photo_path: string | null;
  created_at: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}
