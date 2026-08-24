# Database schema

Source of truth: `supabase/migrations/*.sql` (to be created in implementation step 1). This document is the reference specification of the schema and RLS.

```sql
-- ============ PROFILE ============
profiles (
  id uuid PK references auth.users,
  is_admin boolean default false,  -- bootstrap: exclusively fmazurkiewicz@gmail.com (handle_new_user + seed from auth.users)
  -- Limit of active personas PER ACCOUNT, editable by admin (ADR-12) — replaces
  -- the global constant "5". Lives here (not in usage_limits — PK (user_id, period_start),
  -- reset per period), because it should persist regardless of billing period.
  max_active_personas integer not null default 5,  -- CHECK 0-50
  -- Account settings (ADR-15) — NULL = frontend shows the name from Google OAuth as fallback.
  nick text,
  -- Cost budget in USD per account (ADR-16) — protection against excessive API usage,
  -- NOT a billing/subscription mechanism (no Free/Pro plans). Same pattern
  -- as max_active_personas: persistent regardless of period, editable by admin.
  usage_budget_usd numeric not null default 10.00,  -- CHECK 0-1000
  created_at timestamptz default now()
)

-- ============ TEMPLATES (seed, read-only for user) ============
persona_templates (
  id uuid PK,
  type text,   -- 'personal_trainer'|'dietitian'|...
  default_prompt text,  -- ONLY behavior/style (copied to personas.system_prompt)
  label text,
  created_at timestamptz default now()
)

-- Outside PostgREST — doctor/medications/red flags per template (spec 2026-08-04)
app_private.persona_template_safety (
  template_id uuid PK → persona_templates,
  safety_prompt text not null
)
-- GRANT SELECT only service_role; no anon/authenticated access

plan_templates (
  id uuid PK,
  name text,                 -- "PPL Training", "4 high-protein meals"...
  suggested_for text[],      -- UI hint, not binding structurally
  default_columns jsonb,     -- e.g. ["Exercise","Sets","Reps","Weight","Notes"]
  default_rows jsonb,
  created_at timestamptz default now()
)

-- reference metrics dictionary — log_result validation, with custom fallback.
-- Loaded into backend in-memory cache on startup (hot-path during SSE streaming).
allowed_metrics (
  category text,              -- 'strength'|'diet'|'swimming'|'triathlon'|'badminton'|'custom'
  metric_key text,
  unit text,
  value_type text,            -- 'numeric'|'integer'
  value_min numeric,
  value_max numeric,
  primary key (category, metric_key)
)

-- ============ PERSONAS ============
personas (
  id uuid PK,
  user_id uuid FK -> auth.users,
  type text,
  name text,
  system_prompt text,                          -- ONLY the user-editable section, never platform preamble
  base_template_id uuid FK -> persona_templates,
  plan_template_id uuid FK -> plan_templates,
  template_overrides jsonb,                     -- shape: {"columns": ["…"]} — validated by Pydantic/Zod BEFORE persisting
  detail_level text default 'simple',           -- 'simple'|'detailed'
  custom_result_category text,                  -- required when type='custom' — maps to one of 5 categories or 'custom'
  persona_constraints text,                     -- hard constraints (injuries/recommendations) → planner + ContextBuilder;
                                                -- NOT in PersonaOut / NOT in create|update DTO (system/operator only)
  slug text not null,                           -- ADR-13: stable identifier for "/slug message" in general
                                                -- chat; generated from type+name, regenerated on name change;
                                                -- unique per user (not globally)
  is_shared boolean default false,
  moderation_status text default 'approved',    -- 'pending'|'approved'|'rejected'
  moderation_checked_prompt_hash text,          -- hash of ONLY the user section (not preamble)
  preamble_version int default 1,               -- lets you force a re-check of ALL personas after a platform preamble change
  cloned_from_persona_id uuid FK -> personas nullable,
  active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
)
-- Every EDIT of system_prompt (not only create/share) invalidates hash -> required recheck of moderation before persist.
-- Limit of active personas PER ACCOUNT (profiles.max_active_personas, 5 default, editable by admin —
-- ADR-12): trigger as last line of defense + validation in API (readable message, not 500).

-- ============ USER PROFILE (biometrics, SHARED across all user personas) ============
-- Distinguish from personas.persona_constraints (specific to a given persona; system-level —
-- invisible/inaccessible for end-user in API; e.g. injury set operator-side).
-- reported to gym trainer at the moment). Filled conversationally via `update_user_profile` tool
-- (any persona), with /profile form as fallback — see ai-pipeline.md section 0.
user_profile (
  user_id uuid PK -> auth.users,
  height_cm numeric,             -- 100-250
  weight_kg numeric,              -- 20-400
  date_of_birth date,
  sex text,                       -- 'male'|'female'|'other'
  activity_level text,            -- 'sedentary'|'light'|'moderate'|'active'|'very_active'
  primary_goal text,              -- 'lose_weight'|'build_muscle'|'improve_endurance'|'general_health'|'sport_specific'
  notes text,
  updated_at timestamptz default now()
)

-- ============ CHAT ============
chat_sessions (
  id uuid PK,
  user_id uuid FK,
  persona_id uuid FK nullable,       -- ADR-13: NULL when session_type='general'
  session_type text default 'persona', -- 'persona' (1:1, NOT NULL persona_id) | 'general' (auto-routing, NULL persona_id)
  title text,
  turn_in_progress boolean not null default false,  -- 0008: chat turn in background (SSE disconnect ≠ cancel)
  created_at timestamptz default now(),
  updated_at timestamptz default now()
)
-- WITHOUT rolling summary in MVP (decision) — sliding window of the last M messages when building prompt.
-- CHECK: (session_type='persona' AND persona_id IS NOT NULL) OR (session_type='general' AND persona_id IS NULL).

chat_messages (
  id uuid PK,
  session_id uuid FK,
  role text,                 -- 'user'|'assistant'|'tool'
  content text,
  tool_calls jsonb,
  persona_id uuid FK nullable,  -- ADR-13: attribution per message. In 'general' session different assistant/tool
                                -- messages can have different persona_id; in 'persona' session copies
                                -- session.persona_id (consistent read regardless of session type).
  invoked_via text nullable,    -- ADR-13/17: 'auto_routed' | 'slash_command' | 'multi_slash' | NULL
  created_at timestamptz default now()
)

-- ============ BACKGROUND JOBS (0008) ============
background_jobs (
  id uuid PK,
  user_id uuid FK,
  job_type text,     -- 'plan_generate' | 'plan_harmonize' | 'chat_title'
  status text,       -- 'pending' | 'running' | 'success' | 'error'
  payload jsonb,
  error_message text,
  attempts int,
  created_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz
)
-- RLS: user_id = auth.uid(). Indexes: (user_id, status), pending/running.

-- ============ RESULTS ============
results (
  id uuid PK,
  user_id uuid FK,
  category text,
  metric text,
  value numeric,
  unit text,
  logged_date date,
  source text,                -- 'agent'|'manual'
  source_persona_id uuid FK nullable,
  is_custom boolean default false,   -- metric outside allowed_metrics
  notes text,
  created_at timestamptz default now()
)
create index results_user_category_metric_date
  on results (user_id, category, metric, logged_date);
  -- supports queries for charts in /results (weight, weights, run times trends)

-- ============ PLANS ============
plans (
  id uuid PK,
  user_id uuid FK,
  period_type text,           -- 'week'|'month'
  start_date date,
  end_date date,
  status text,                -- 'generating'|'ready'|'partial_ready'|'error'
  created_at timestamptz default now(),
  updated_at timestamptz default now()
)

plan_items (
  id uuid PK,
  plan_id uuid FK,
  item_date date,
  item_type text,
  persona_id uuid FK,
  content jsonb,               -- {title, columns, rows, notes} — FROZEN snapshot,
                                -- never live-ref to plan_templates/personas.template_overrides
  schema_version int default 1,  -- lets you safely evolve the JSON shape in the future
  created_at timestamptz default now()
)

plan_generation_jobs (
  id uuid PK,
  plan_id uuid FK,
  status text,                 -- 'pending'|'running'|'success'|'partial_success'|'error'  (derivative of per-persona state)
  error_message text,
  attempts int default 0,
  created_at timestamptz default now(),
  started_at timestamptz,
  finished_at timestamptz
)

plan_generation_job_personas (
  job_id uuid FK -> plan_generation_jobs,
  persona_id uuid FK -> personas,
  status text,                 -- 'pending'|'running'|'done'|'failed'
  retry_count int default 0,
  last_error text,
  primary key (job_id, persona_id)
)

-- Enforced at database level, not check-then-insert in application (race condition):
create unique index one_active_job_per_user
  on plan_generation_jobs (plan_id)
  where status in ('pending', 'running');
-- note: uniqueness per-user (not per-plan) requires join with `plans` on insert -- consider trigger
-- BEFORE INSERT checking existence of an active job for user_id from plans.

-- ============ EXERCISE CATALOG (ADR-14, amended 2026-08-23) ============
-- Reference content (like persona_templates/plan_templates), seeded via migration,
-- read-only for user. Tied to persona type (visible in /settings for personas
-- of type motor_coach/badminton_coach — see frontend.md).
-- Scale after free-exercise-db import: ~873 entries (868 imported + manual badminton_coach).
exercises (
  id uuid PK,
  slug text unique,
  name text,                   -- PL (LLM translation in seed 0013)
  name_en text,                -- EN original — matcher for clickable names in plans
  persona_type text,           -- personas.type for which the exercise is visible
  level text,                  -- 'beginner'|'intermediate'|'advanced'
  categories text[],           -- PL labels (muscles + workout type), no lookup table
  short_description text,
  detail_full text,            -- "Execution" (numbered steps for import)
  common_mistakes text,        -- "Common mistakes"; NULL for import from free-exercise-db
  photo_path text,             -- path in 'exercise-photos' bucket (e.g. free-exercise-db/<Id>/0.jpg); API composes public URL
  source text default 'manual',-- 'manual' | 'free_exercise_db' (0012)
  created_at timestamptz default now()
)

-- ============ LIMITS ============
usage_limits (
  user_id uuid FK,
  period_start date,
  messages_used int default 0,
  tokens_used int default 0,
  plan_generations_used int default 0,   -- plan generation debits from THIS SAME limiter as chat
  cost_usd_used numeric default 0,       -- ADR-16: actual cost (USD) in current period, counted from
                                          -- prompt_tokens/completion_tokens × model pricing (OpenRouter
                                          -- /api/v1/models, cached) — enforced against
                                          -- profiles.usage_budget_usd (429 on exceeding)
  primary key (user_id, period_start)
)
-- `tier` (Free/Pro plans concept) REMOVED (ADR-16) — limit is an explicit USD budget per account
-- (profiles.usage_budget_usd), not a subscription plan.

-- ============ SECURITY / MODERATION ============
moderation_events (
  id uuid PK,
  user_id uuid FK,
  persona_id uuid FK nullable,
  session_id uuid FK nullable,
  message_id uuid FK nullable,
  trigger_type text,           -- 'persona_create'|'persona_edit'|'persona_share'|'chat_heuristic'|'chat_classifier'
  raw_snippet text,             -- GDPR WARNING: may contain sensitive content (red flags) — see security.md (retention/RBAC)
  classifier_verdict text,     -- 'clean'|'injection_attempt'|'redefine_role'|'off_topic'
  reviewed boolean default false,
  created_at timestamptz default now()
)

admin_audit_log (
  id uuid PK,
  admin_user_id uuid FK,
  action text,                 -- 'reset_password'|'edit_limits'|'edit_persona_limit'|...
  target_user_id uuid,
  details jsonb,
  created_at timestamptz default now()
)
```

## RLS (Row Level Security)

| Table | Policy |
|---|---|
| `persona_templates`, `plan_templates`, `allowed_metrics`, `exercises` | SELECT public, no INSERT/UPDATE/DELETE for user |
| `personas` | `user_id = auth.uid()` for everything + additionally SELECT when `is_shared=true AND moderation_status='approved'` (community, read only, never UPDATE/DELETE on someone else's persona) |
| `profiles`, `user_profile`, `chat_sessions`, `chat_messages`, `results`, `plans`, `plan_items`, `usage_limits` | strictly `user_id = auth.uid()` |
| `plan_generation_jobs`, `plan_generation_job_personas` | access via join with `plans.user_id = auth.uid()` |
| `moderation_events`, `admin_audit_log` | no access for regular user — only backend in the context of `/admin/*` with explicit verification of `profiles.is_admin` |

Cloning personas from community creates a **new record** with `user_id = auth.uid()`, never modifies the original.
