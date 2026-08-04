# Schemat bazy danych

Źródło prawdy: `supabase/migrations/*.sql` (do utworzenia w kroku 1 implementacji). Ten dokument to specyfikacja referencyjna schematu i RLS.

```sql
-- ============ PROFIL ============
profiles (
  id uuid PK references auth.users,
  is_admin boolean default false,  -- bootstrap: wyłącznie fmazurkiewicz@gmail.com (handle_new_user + seed z auth.users)
  -- Limit aktywnych person PER KONTO, edytowalny przez admina (ADR-12) — zastępuje
  -- globalną stałą "5". Żyje tu (nie w usage_limits — PK (user_id, period_start),
  -- resetowane co okres), bo ma trwać niezależnie od okresu rozliczeniowego.
  max_active_personas integer not null default 5,  -- CHECK 0-50
  -- Ustawienia konta (ADR-15) — NULL = frontend pokazuje nazwę z Google OAuth jako fallback.
  nick text,
  -- Budżet kosztowy w USD per konto (ADR-16) — ochrona przed nadmiernym zużyciem API,
  -- NIE mechanizm rozliczeniowy/subskrypcyjny (brak planów Free/Pro). Ten sam wzorzec
  -- co max_active_personas: trwały niezależnie od okresu, edytowalny przez admina.
  usage_budget_usd numeric not null default 10.00,  -- CHECK 0-1000
  created_at timestamptz default now()
)

-- ============ GOTOWCE (seed, read-only dla usera) ============
persona_templates (
  id uuid PK,
  type text,   -- 'personal_trainer'|'dietitian'|...
  default_prompt text,  -- TYLKO zachowanie/styl (kopiowane do personas.system_prompt)
  label text,
  created_at timestamptz default now()
)

-- Poza PostgREST — lekarz/leki/red flags per gotowiec (spec 2026-08-04)
app_private.persona_template_safety (
  template_id uuid PK → persona_templates,
  safety_prompt text not null
)
-- GRANT SELECT wyłącznie service_role; brak dostępu anon/authenticated

plan_templates (
  id uuid PK,
  name text,                 -- "Trening PPL", "4 posiłki wysokobiałkowe"...
  suggested_for text[],      -- podpowiedź UI, niewiążąca strukturalnie
  default_columns jsonb,     -- np. ["Ćwiczenie","Serie","Powtórzenia","Ciężar","Uwagi"]
  default_rows jsonb,
  created_at timestamptz default now()
)

-- referencyjny słownik metryk — walidacja log_result, z fallbackiem na custom.
-- Ładowana do cache in-memory backendu na starcie (hot-path w trakcie streamingu SSE).
allowed_metrics (
  category text,              -- 'strength'|'diet'|'swimming'|'triathlon'|'badminton'|'custom'
  metric_key text,
  unit text,
  value_type text,            -- 'numeric'|'integer'
  value_min numeric,
  value_max numeric,
  primary key (category, metric_key)
)

-- ============ PERSONY ============
personas (
  id uuid PK,
  user_id uuid FK -> auth.users,
  type text,
  name text,
  system_prompt text,                          -- WYŁĄCZNIE sekcja edytowalna usera, nigdy platform preambuł
  base_template_id uuid FK -> persona_templates,
  plan_template_id uuid FK -> plan_templates,
  template_overrides jsonb,                     -- kształt: {"columns": ["…"]} — walidowane Pydantic/Zod PRZED zapisem
  detail_level text default 'simple',           -- 'simple'|'detailed'
  custom_result_category text,                  -- wymagane gdy type='custom' — mapowanie na 1 z 5 kategorii albo 'custom'
  persona_constraints text,                     -- twarde ograniczenia (kontuzje/zalecenia) → planner + ContextBuilder;
                                                 -- NIE w PersonaOut / NIE w create|update DTO (tylko system/operator)
  slug text not null,                           -- ADR-13: stabilny identyfikator do "/slug wiadomość" w ogólnym
                                                 -- czacie; generowany z type+name, regenerowany przy zmianie nazwy;
                                                 -- unikalny per user (nie globalnie)
  is_shared boolean default false,
  moderation_status text default 'approved',    -- 'pending'|'approved'|'rejected'
  moderation_checked_prompt_hash text,          -- hash TYLKO sekcji usera (nie preambułu)
  preamble_version int default 1,               -- pozwala wymusić re-check WSZYSTKICH person po zmianie preambułu platformy
  cloned_from_persona_id uuid FK -> personas nullable,
  active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
)
-- Każda EDYCJA system_prompt (nie tylko create/share) invaliduje hash -> wymagany recheck moderacji przed zapisem.
-- Limit aktywnych person PER KONTO (profiles.max_active_personas, domyślnie 5, edytowalny przez admina —
-- ADR-12): trigger jako ostatnia linia obrony + walidacja w API (czytelny komunikat, nie 500).

-- ============ PROFIL UŻYTKOWNIKA (biometria, WSPÓLNY dla wszystkich person usera) ============
-- Odróżnij od personas.persona_constraints (specyficzne dla danej persony; systemowe —
-- niewidoczne/niedostępne dla end-usera w API; np. kontuzja ustawiona operatorsko).
-- zgłoszona akurat trenerowi siłowni). Wypełniany konwersacyjnie przez tool `update_user_profile`
-- (dowolna persona), z formularzem /profile jako fallback — patrz ai-pipeline.md sekcja 0.
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

-- ============ CZAT ============
chat_sessions (
  id uuid PK,
  user_id uuid FK,
  persona_id uuid FK nullable,       -- ADR-13: NULL gdy session_type='general'
  session_type text default 'persona', -- 'persona' (1:1, NOT NULL persona_id) | 'general' (auto-routing, NULL persona_id)
  title text,
  turn_in_progress boolean not null default false,  -- 0008: tura czatu w tle (SSE disconnect ≠ cancel)
  created_at timestamptz default now(),
  updated_at timestamptz default now()
)
-- BEZ rolling summary w MVP (decyzja) — sam sliding window ostatnich M wiadomości przy budowaniu promptu.
-- CHECK: (session_type='persona' AND persona_id IS NOT NULL) OR (session_type='general' AND persona_id IS NULL).

chat_messages (
  id uuid PK,
  session_id uuid FK,
  role text,                 -- 'user'|'assistant'|'tool'
  content text,
  tool_calls jsonb,
  persona_id uuid FK nullable,  -- ADR-13: atrybucja per wiadomość. W sesji 'general' różne wiadomości
                                 -- assistant/tool mogą mieć różny persona_id; w sesji 'persona' kopiuje
                                 -- session.persona_id (spójny odczyt niezależnie od typu sesji).
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
-- RLS: user_id = auth.uid(). Indeksy: (user_id, status), pending/running.

-- ============ WYNIKI ============
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
  is_custom boolean default false,   -- metryka spoza allowed_metrics
  notes text,
  created_at timestamptz default now()
)
create index results_user_category_metric_date
  on results (user_id, category, metric, logged_date);
  -- wspiera zapytania pod wykresy w /results (trend wagi, ciężarów, czasów biegowych)

-- ============ PLANY ============
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
  content jsonb,               -- {title, columns, rows, notes} — ZAMROŻONY snapshot,
                                -- nigdy live-ref do plan_templates/personas.template_overrides
  schema_version int default 1,  -- pozwala bezpiecznie ewoluować kształt JSON w przyszłości
  created_at timestamptz default now()
)

plan_generation_jobs (
  id uuid PK,
  plan_id uuid FK,
  status text,                 -- 'pending'|'running'|'success'|'partial_success'|'error'  (pochodna stanu per-persona)
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

-- Egzekwowane na poziomie bazy, nie check-then-insert w aplikacji (race condition):
create unique index one_active_job_per_user
  on plan_generation_jobs (plan_id)
  where status in ('pending', 'running');
-- uwaga: unikalność per-user (nie per-plan) wymaga join z `plans` przy insert -- rozważyć trigger
-- BEFORE INSERT sprawdzający istnienie aktywnego jobu dla user_id z plans.

-- ============ KATALOG ĆWICZEŃ (ADR-14) ============
-- Treść referencyjna (jak persona_templates/plan_templates), seedowana migracją,
-- read-only dla usera. Powiązana z typem persony (widoczna w /settings dla person
-- typu motor_coach/badminton_coach — patrz frontend.md).
exercises (
  id uuid PK,
  slug text unique,
  name text,
  persona_type text,           -- personas.type, dla którego ćwiczenie jest widoczne
  level text,                  -- 'beginner'|'intermediate'|'advanced'
  categories text[],           -- np. ['Nogi','Plecy'] — mała, znana z góry lista, bez tabeli słownikowej
  short_description text,
  detail_full text,            -- "Wykonanie"
  common_mistakes text,        -- "Częste błędy"
  photo_path text,             -- ścieżka w Supabase Storage (bucket publiczny 'exercise-photos'), nullable
  created_at timestamptz default now()
)

-- ============ LIMITY ============
usage_limits (
  user_id uuid FK,
  period_start date,
  messages_used int default 0,
  tokens_used int default 0,
  plan_generations_used int default 0,   -- generowanie planu debituje z TEGO SAMEGO limitera co czat
  cost_usd_used numeric default 0,       -- ADR-16: faktyczny koszt (USD) w bieżącym okresie, liczony z
                                          -- prompt_tokens/completion_tokens × cennik modelu (OpenRouter
                                          -- /api/v1/models, cache'owany) — egzekwowany względem
                                          -- profiles.usage_budget_usd (429 po przekroczeniu)
  primary key (user_id, period_start)
)
-- `tier` (koncept planów Free/Pro) USUNIĘTY (ADR-16) — limit to jawny budżet USD per konto
-- (profiles.usage_budget_usd), nie plan subskrypcyjny.

-- ============ BEZPIECZEŃSTWO / MODERACJA ============
moderation_events (
  id uuid PK,
  user_id uuid FK,
  persona_id uuid FK nullable,
  session_id uuid FK nullable,
  message_id uuid FK nullable,
  trigger_type text,           -- 'persona_create'|'persona_edit'|'persona_share'|'chat_heuristic'|'chat_classifier'
  raw_snippet text,             -- UWAGA RODO: może zawierać wrażliwe treści (red flags) — patrz security.md (retencja/RBAC)
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

| Tabela | Polityka |
|---|---|
| `persona_templates`, `plan_templates`, `allowed_metrics`, `exercises` | SELECT publiczne, brak INSERT/UPDATE/DELETE dla usera |
| `personas` | `user_id = auth.uid()` dla wszystkiego + dodatkowo SELECT gdy `is_shared=true AND moderation_status='approved'` (community, tylko odczyt, nigdy UPDATE/DELETE cudzej persony) |
| `profiles`, `user_profile`, `chat_sessions`, `chat_messages`, `results`, `plans`, `plan_items`, `usage_limits` | ściśle `user_id = auth.uid()` |
| `plan_generation_jobs`, `plan_generation_job_personas` | dostęp przez join z `plans.user_id = auth.uid()` |
| `moderation_events`, `admin_audit_log` | brak dostępu dla zwykłego usera — tylko backend w kontekście `/admin/*` z jawną weryfikacją `profiles.is_admin` |

Klonowanie person z community tworzy **nowy rekord** z `user_id = auth.uid()`, nigdy nie modyfikuje oryginału.
