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

export interface TemplateOverrideColumn {
  name: string;
}

export interface Persona {
  id: string;
  user_id: string;
  type: PersonaType;
  name: string;
  system_prompt: string;
  base_template_id: string | null;
  chat_model: string;
  plan_template_id: string | null;
  template_overrides: TemplateOverrideColumn[] | null;
  detail_level: DetailLevel;
  custom_result_category: string | null;
  persona_constraints: string | null;
  is_shared: boolean;
  moderation_status: ModerationStatus;
  cloned_from_persona_id: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export type ChatRole = "user" | "assistant" | "tool";

export interface ChatSession {
  id: string;
  user_id: string;
  persona_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: ChatRole;
  content: string;
  tool_calls: unknown | null;
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

export interface UsageLimits {
  user_id: string;
  period_start: string;
  messages_used: number;
  tokens_used: number;
  plan_generations_used: number;
  tier: "free";
}

// Profil biometryczny — WSPÓLNY dla wszystkich person usera (odróżnij od
// Persona.persona_constraints, specyficznego dla danej persony). Wypełniany docelowo
// konwersacyjnie (tool `update_user_profile` w dowolnej rozmowie) — ten typ opisuje
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
// admina (nie globalna stała), patrz docs/adr/decisions.md ADR-12.
export interface AdminUser {
  id: string;
  is_admin: boolean;
  max_active_personas: number;
  created_at: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}
