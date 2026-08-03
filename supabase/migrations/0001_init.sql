-- Multi-Persona Coaching App — schemat początkowy (skonsolidowany)
-- Źródło prawdy: docs/technical/database-schema.md, docs/adr/decisions.md
-- Supabase włącza pgcrypto domyślnie (gen_random_uuid()).
--
-- UWAGA: to jest jedyna migracja bazowa (nic nie zostało jeszcze uruchomione/wdrożone,
-- więc historia ALTER-ów z wczesnych iteracji projektu została scalona w jeden spójny
-- init zamiast trzymana jako osobne, przyrostowe pliki). Kolejne migracje dodają wyłącznie
-- nowe, samodzielne domeny (patrz 0002_exercise_catalog.sql).

-- ============================================================
-- PROFIL
-- ============================================================

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  is_admin boolean not null default false,
  -- Limit aktywnych person PER KONTO, edytowalny przez admina (ADR-12) — nie globalna stała.
  max_active_personas integer not null default 5
    constraint max_active_personas_range check (max_active_personas between 0 and 50),
  -- Ustawienia konta (ADR-15) — NULL = frontend pokazuje nazwę z Google OAuth jako fallback.
  nick text,
  -- Budżet kosztowy w USD per konto (ADR-16) — ochrona przed nadmiernym zużyciem API,
  -- NIE mechanizm rozliczeniowy/subskrypcyjny (brak planów Free/Pro). Edytowalny przez admina.
  usage_budget_usd numeric not null default 10.00
    constraint usage_budget_usd_range check (usage_budget_usd between 0 and 1000),
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy profiles_select_own on public.profiles
  for select using (id = auth.uid());

create policy profiles_update_own on public.profiles
  for update using (id = auth.uid())
  with check (id = auth.uid());

-- Auto-tworzenie wiersza profiles przy rejestracji (standardowy wzorzec Supabase).
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================================
-- GOTOWCE (seed, read-only dla usera)
-- ============================================================

create table public.persona_templates (
  id uuid primary key default gen_random_uuid(),
  type text not null,
  default_prompt text not null,
  label text not null,
  created_at timestamptz not null default now()
);

alter table public.persona_templates enable row level security;
create policy persona_templates_select_all on public.persona_templates
  for select using (true);

create table public.plan_templates (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  suggested_for text[] not null default '{}',
  default_columns jsonb not null,
  default_rows jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.plan_templates enable row level security;
create policy plan_templates_select_all on public.plan_templates
  for select using (true);

-- Słownik referencyjny metryk — walidacja log_result, cache in-memory po stronie backendu.
create table public.allowed_metrics (
  category text not null,
  metric_key text not null,
  unit text not null,
  value_type text not null default 'numeric', -- 'numeric' | 'integer'
  value_min numeric,
  value_max numeric,
  primary key (category, metric_key)
);

alter table public.allowed_metrics enable row level security;
create policy allowed_metrics_select_all on public.allowed_metrics
  for select using (true);

-- ============================================================
-- PERSONY
-- ============================================================

create table public.personas (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  type text not null,
  name text not null,
  system_prompt text not null default '',            -- WYŁĄCZNIE sekcja edytowalna usera, nigdy platform preambuł
  base_template_id uuid references public.persona_templates (id),
  chat_model text not null default 'anthropic/claude-haiku-4.5',
  plan_template_id uuid references public.plan_templates (id),
  template_overrides jsonb,                          -- walidowane Pydantic/Zod przed zapisem (fail fast)
  detail_level text not null default 'simple',       -- 'simple' | 'detailed'
  custom_result_category text,                       -- wymagane w API gdy type='custom'
  persona_constraints text,                          -- twarde ograniczenia (kontuzje itp.) przekazywane wprost do plannera
  -- Stabilny identyfikator do "/slug wiadomość" w ogólnym czacie (ADR-13) — generowany
  -- z type+name przy tworzeniu, regenerowany przy zmianie nazwy (kolizje -> numeryczny suffix).
  slug text not null,
  is_shared boolean not null default false,
  moderation_status text not null default 'approved', -- 'pending' | 'approved' | 'rejected'
  moderation_checked_prompt_hash text,                -- hash TYLKO sekcji usera
  preamble_version int not null default 1,            -- wymusza re-check po zmianie platform preambułu
  cloned_from_persona_id uuid references public.personas (id),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint detail_level_check check (detail_level in ('simple', 'detailed')),
  constraint moderation_status_check check (moderation_status in ('pending', 'approved', 'rejected')),
  constraint personas_slug_format_check check (slug ~ '^[a-z0-9_]+$')
);

create index personas_user_id_idx on public.personas (user_id);
create index personas_community_idx on public.personas (is_shared, moderation_status) where is_shared = true;
create unique index personas_user_slug_unique_idx on public.personas (user_id, slug);

alter table public.personas enable row level security;

create policy personas_select_own on public.personas
  for select using (user_id = auth.uid());

create policy personas_select_shared on public.personas
  for select using (is_shared = true and moderation_status = 'approved');

create policy personas_insert_own on public.personas
  for insert with check (user_id = auth.uid());

create policy personas_update_own on public.personas
  for update using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy personas_delete_own on public.personas
  for delete using (user_id = auth.uid());

-- Limit aktywnych person PER KONTO (profiles.max_active_personas, ADR-12) — trigger jako
-- ostatnia linia obrony (API waliduje to samo z czytelnym komunikatem przed uderzeniem w bazę).
create or replace function public.enforce_persona_limit()
returns trigger
language plpgsql
as $$
declare
  active_count integer;
  max_allowed integer;
begin
  if new.active = true then
    select max_active_personas into max_allowed
    from public.profiles
    where id = new.user_id;

    select count(*) into active_count
    from public.personas
    where user_id = new.user_id
      and active = true
      and id <> coalesce(new.id, '00000000-0000-0000-0000-000000000000'::uuid);

    if active_count >= coalesce(max_allowed, 5) then
      raise exception 'persona_limit_exceeded' using errcode = 'P0001';
    end if;
  end if;
  return new;
end;
$$;

create trigger trg_persona_limit
  before insert or update of active on public.personas
  for each row
  when (new.active = true)
  execute function public.enforce_persona_limit();

-- ============================================================
-- PROFIL UŻYTKOWNIKA (biometria, WSPÓLNY dla wszystkich person usera)
-- ============================================================
-- Odróżnij od personas.persona_constraints (specyficzne dla danej persony, np. kontuzja
-- zgłoszona akurat trenerowi siłowni). Wypełniany docelowo KONWERSACYJNIE — dowolna persona
-- woła tool `update_user_profile`, z formularzem /profile jako fallback. ai-pipeline.md §0, ADR-11.

create table public.user_profile (
  user_id uuid primary key references auth.users (id) on delete cascade,
  height_cm numeric,
  weight_kg numeric,
  date_of_birth date,
  sex text,                     -- 'male' | 'female' | 'other'
  activity_level text,          -- 'sedentary' | 'light' | 'moderate' | 'active' | 'very_active'
  primary_goal text,            -- 'lose_weight' | 'build_muscle' | 'improve_endurance' | 'general_health' | 'sport_specific'
  notes text,
  updated_at timestamptz not null default now(),
  constraint height_cm_range check (height_cm is null or (height_cm between 100 and 250)),
  constraint weight_kg_range check (weight_kg is null or (weight_kg between 20 and 400)),
  constraint sex_check check (sex is null or sex in ('male', 'female', 'other')),
  constraint activity_level_check check (
    activity_level is null or activity_level in ('sedentary', 'light', 'moderate', 'active', 'very_active')
  ),
  constraint primary_goal_check check (
    primary_goal is null or primary_goal in
      ('lose_weight', 'build_muscle', 'improve_endurance', 'general_health', 'sport_specific')
  )
);

alter table public.user_profile enable row level security;
create policy user_profile_all_own on public.user_profile
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ============================================================
-- CZAT
-- ============================================================
-- Sesja 'persona' (1:1, persona_id NOT NULL) obok sesji 'general' (auto-routing,
-- persona_id IS NULL) — ADR-13. Atrybucja per wiadomość w chat_messages.persona_id,
-- bo w sesji 'general' różne wiadomości assistant/tool mogą pochodzić od różnych person.

create table public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  persona_id uuid references public.personas (id) on delete cascade,
  session_type text not null default 'persona',
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint chat_sessions_type_check check (session_type in ('persona', 'general')),
  constraint chat_sessions_type_persona_id_check check (
    (session_type = 'persona' and persona_id is not null)
    or (session_type = 'general' and persona_id is null)
  )
);
-- Bez rolling summary w MVP (ADR-7) — sam sliding window przy budowaniu promptu.

create index chat_sessions_user_id_idx on public.chat_sessions (user_id);
create index chat_sessions_persona_id_idx on public.chat_sessions (persona_id);

alter table public.chat_sessions enable row level security;
create policy chat_sessions_all_own on public.chat_sessions
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

create table public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.chat_sessions (id) on delete cascade,
  role text not null,                                 -- 'user' | 'assistant' | 'tool'
  content text,
  tool_calls jsonb,
  -- Atrybucja per wiadomość (ADR-13) — w sesji 'general' różne wiadomości assistant/tool
  -- mogą mieć różny persona_id; w sesji 'persona' kopiuje session.persona_id (spójny odczyt
  -- niezależnie od typu sesji, bez if/else w repozytorium).
  persona_id uuid references public.personas (id),
  invoked_via text,                                   -- 'auto_routed' | 'slash_command' | NULL
  created_at timestamptz not null default now(),
  constraint role_check check (role in ('user', 'assistant', 'tool')),
  constraint chat_messages_invoked_via_check check (invoked_via is null or invoked_via in ('auto_routed', 'slash_command'))
);

create index chat_messages_session_id_idx on public.chat_messages (session_id, created_at);
create index chat_messages_persona_id_idx on public.chat_messages (persona_id);

alter table public.chat_messages enable row level security;
create policy chat_messages_all_own on public.chat_messages
  for all
  using (exists (
    select 1 from public.chat_sessions s
    where s.id = chat_messages.session_id and s.user_id = auth.uid()
  ))
  with check (exists (
    select 1 from public.chat_sessions s
    where s.id = chat_messages.session_id and s.user_id = auth.uid()
  ));

-- ============================================================
-- WYNIKI
-- ============================================================

create table public.results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  category text not null,          -- 'strength'|'diet'|'swimming'|'triathlon'|'badminton'|'custom'
  metric text not null,
  value numeric not null,
  unit text,
  logged_date date not null,
  source text not null default 'manual',   -- 'agent' | 'manual'
  source_persona_id uuid references public.personas (id),
  is_custom boolean not null default false,  -- metryka spoza allowed_metrics
  notes text,
  created_at timestamptz not null default now(),
  constraint source_check check (source in ('agent', 'manual'))
);

-- Wspiera zapytania pod wykresy w /results (trend wagi, ciężarów, czasów biegowych)
-- oraz walidację/agregację per kategoria+metryka.
create index results_user_category_metric_date_idx
  on public.results (user_id, category, metric, logged_date);

alter table public.results enable row level security;
create policy results_all_own on public.results
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ============================================================
-- PLANY
-- ============================================================

create table public.plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  period_type text not null,        -- 'week' | 'month'
  start_date date not null,
  end_date date not null,
  status text not null default 'generating', -- 'generating'|'ready'|'partial_ready'|'error'
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint period_type_check check (period_type in ('week', 'month')),
  constraint plan_status_check check (status in ('generating', 'ready', 'partial_ready', 'error'))
);

create index plans_user_id_idx on public.plans (user_id, start_date);

alter table public.plans enable row level security;
create policy plans_all_own on public.plans
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

create table public.plan_items (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references public.plans (id) on delete cascade,
  item_date date not null,
  item_type text not null,
  persona_id uuid not null references public.personas (id),
  content jsonb not null,           -- {title, columns, rows, notes} — ZAMROŻONY snapshot
  schema_version int not null default 1,
  created_at timestamptz not null default now()
);

create index plan_items_plan_id_idx on public.plan_items (plan_id, item_date);

alter table public.plan_items enable row level security;
create policy plan_items_all_own on public.plan_items
  for all
  using (exists (select 1 from public.plans p where p.id = plan_items.plan_id and p.user_id = auth.uid()))
  with check (exists (select 1 from public.plans p where p.id = plan_items.plan_id and p.user_id = auth.uid()));

-- Denormalizowany user_id (nie tylko plan_id) — pozwala na prosty unique index
-- "1 aktywny job na usera" bez joina przy insert.
create table public.plan_generation_jobs (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references public.plans (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  status text not null default 'pending', -- 'pending'|'running'|'success'|'partial_success'|'error'
  error_message text,
  attempts int not null default 0,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  constraint job_status_check check (status in ('pending', 'running', 'success', 'partial_success', 'error'))
);

-- Egzekwowane na poziomie bazy, nie check-then-insert w aplikacji (race condition).
create unique index one_active_job_per_user
  on public.plan_generation_jobs (user_id)
  where status in ('pending', 'running');

alter table public.plan_generation_jobs enable row level security;
create policy plan_generation_jobs_all_own on public.plan_generation_jobs
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

create table public.plan_generation_job_personas (
  job_id uuid not null references public.plan_generation_jobs (id) on delete cascade,
  persona_id uuid not null references public.personas (id),
  status text not null default 'pending', -- 'pending'|'running'|'done'|'failed'
  retry_count int not null default 0,
  last_error text,
  primary key (job_id, persona_id),
  constraint job_persona_status_check check (status in ('pending', 'running', 'done', 'failed'))
);

alter table public.plan_generation_job_personas enable row level security;
create policy plan_generation_job_personas_all_own on public.plan_generation_job_personas
  for all
  using (exists (
    select 1 from public.plan_generation_jobs j
    where j.id = plan_generation_job_personas.job_id and j.user_id = auth.uid()
  ))
  with check (exists (
    select 1 from public.plan_generation_jobs j
    where j.id = plan_generation_job_personas.job_id and j.user_id = auth.uid()
  ));

-- ============================================================
-- LIMITY (budżet USD per konto — ADR-16)
-- ============================================================

create table public.usage_limits (
  user_id uuid not null references auth.users (id) on delete cascade,
  period_start date not null,
  messages_used int not null default 0,
  tokens_used int not null default 0,
  plan_generations_used int not null default 0,  -- generowanie planu debituje z tego samego limitera co czat
  -- Faktyczny koszt (USD) w bieżącym okresie, liczony z prompt_tokens/completion_tokens ×
  -- cennik modelu (OpenRouter /api/v1/models, cache'owany) — egzekwowany względem
  -- profiles.usage_budget_usd. Brak kolumny `tier` — to nie plan subskrypcyjny (ADR-16).
  cost_usd_used numeric not null default 0,
  primary key (user_id, period_start)
);

alter table public.usage_limits enable row level security;
create policy usage_limits_select_own on public.usage_limits
  for select using (user_id = auth.uid());
-- Insert/update wyłącznie przez backend jako authenticated user w kontekście RLS danego usera
-- (increment happens server-side, nie bezpośrednio z frontendu) — polityka analogiczna do select.
create policy usage_limits_write_own on public.usage_limits
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ============================================================
-- BEZPIECZEŃSTWO / MODERACJA (brak dostępu dla zwykłego usera)
-- ============================================================

create table public.moderation_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  persona_id uuid references public.personas (id),
  session_id uuid references public.chat_sessions (id),
  message_id uuid references public.chat_messages (id),
  trigger_type text not null, -- 'persona_create'|'persona_edit'|'persona_share'|'chat_heuristic'|'chat_classifier'
  raw_snippet text,           -- UWAGA RODO: może zawierać wrażliwe treści — patrz docs/technical/security.md
  classifier_verdict text,    -- 'clean'|'injection_attempt'|'redefine_role'|'off_topic'
  reviewed boolean not null default false,
  created_at timestamptz not null default now()
);

alter table public.moderation_events enable row level security;
-- Brak polityk SELECT/INSERT dla roli `authenticated` — dostęp wyłącznie przez service_role
-- (backend w kontekście /admin/*), zgodnie z docs/technical/security.md.

create table public.admin_audit_log (
  id uuid primary key default gen_random_uuid(),
  admin_user_id uuid not null references auth.users (id),
  action text not null,           -- 'reset_password'|'edit_persona_limit'|'edit_usage_budget'|...
  target_user_id uuid,
  details jsonb,
  created_at timestamptz not null default now()
);

alter table public.admin_audit_log enable row level security;
-- Brak polityk dla `authenticated` — wyłącznie service_role.

-- ============================================================
-- SEED DATA
-- ============================================================

insert into public.persona_templates (type, label, default_prompt) values
  ('personal_trainer', 'Trener personalny',
   'Jesteś doświadczonym trenerem personalnym. Pomagasz użytkownikowi budować siłę, '
   || 'poprawną technikę i konsekwencję treningową. Dostosowujesz plany do poziomu '
   || 'zaawansowania i dostępnego sprzętu.'),
  ('dietitian', 'Dietetyk',
   'Jesteś dietetykiem sportowym. Pomagasz układać jadłospis wspierający cele treningowe '
   || 'użytkownika (redukcja, masa, wydolność), tłumaczysz wybory żywieniowe w prosty sposób.'),
  ('sport_psychologist', 'Psycholog sportowy',
   'Jesteś psychologiem sportowym. Pomagasz z motywacją, radzeniem sobie ze stresem '
   || 'startowym, budowaniem nawyków treningowych i odpornością psychiczną w kontekście sportu.'),
  ('psychologist', 'Psycholog',
   'Jesteś psychologiem wspierającym w kontekście ogólnego dobrostanu związanego '
   || 'z aktywnością fizyczną i zdrowym stylem życia.'),
  ('motor_coach', 'Trener motoryczny',
   'Jesteś trenerem przygotowania motorycznego. Skupiasz się na mobilności, koordynacji, '
   || 'sile funkcjonalnej i prewencji kontuzji.'),
  ('badminton_coach', 'Trener badmintona',
   'Jesteś trenerem badmintona. Pomagasz rozwijać technikę uderzeń, taktykę meczową '
   || 'i kondycję specyficzną dla tego sportu.');

insert into public.plan_templates (name, suggested_for, default_columns, default_rows) values
  ('Trening siłowy — Push/Pull/Legs', array['personal_trainer', 'motor_coach'],
   '["Ćwiczenie", "Serie", "Powtórzenia", "Ciężar", "Uwagi"]'::jsonb, '[]'::jsonb),
  ('4 posiłki, wysokie białko', array['dietitian'],
   '["Posiłek", "Porcja", "Białko", "Węgle", "Tłuszcz", "Kcal"]'::jsonb, '[]'::jsonb),
  ('Trening badmintona — technika', array['badminton_coach'],
   '["Ćwiczenie", "Czas/Powtórzenia", "Intensywność", "Uwagi"]'::jsonb, '[]'::jsonb),
  ('Sesja mentalna', array['sport_psychologist', 'psychologist'],
   '["Temat", "Ćwiczenie/Technika", "Czas trwania", "Notatki"]'::jsonb, '[]'::jsonb);

insert into public.allowed_metrics (category, metric_key, unit, value_type, value_min, value_max) values
  ('strength', 'weight_kg', 'kg', 'numeric', 20, 400),
  ('strength', 'reps', 'reps', 'integer', 1, 100),
  ('strength', 'sets', 'sets', 'integer', 1, 20),
  ('strength', 'bench_press_1rm', 'kg', 'numeric', 10, 400),
  ('strength', 'squat_1rm', 'kg', 'numeric', 10, 500),
  ('strength', 'deadlift_1rm', 'kg', 'numeric', 10, 500),
  ('diet', 'weight_kg', 'kg', 'numeric', 30, 300),
  ('diet', 'calories', 'kcal', 'numeric', 0, 10000),
  ('diet', 'protein_g', 'g', 'numeric', 0, 500),
  ('diet', 'carbs_g', 'g', 'numeric', 0, 1000),
  ('diet', 'fat_g', 'g', 'numeric', 0, 400),
  ('swimming', 'distance_m', 'm', 'numeric', 0, 20000),
  ('swimming', 'duration_min', 'min', 'numeric', 0, 300),
  ('triathlon', 'run_time_min', 'min', 'numeric', 0, 600),
  ('triathlon', 'bike_distance_km', 'km', 'numeric', 0, 300),
  ('badminton', 'training_minutes', 'min', 'numeric', 0, 300),
  ('badminton', 'match_score', 'points', 'integer', 0, 30);
