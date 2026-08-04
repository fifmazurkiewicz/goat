-- 0008: Kolejka zadań w tle (Postgres) + flaga tury czatu na sesji.
-- Uruchom w Supabase SQL Editor po 0007 (lokalnie: psql -f ...).

alter table public.chat_sessions
  add column if not exists turn_in_progress boolean not null default false;

create table if not exists public.background_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  job_type text not null,
  status text not null default 'pending',
  payload jsonb not null default '{}'::jsonb,
  error_message text,
  attempts int not null default 0,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  constraint background_jobs_type_check check (
    job_type in ('plan_generate', 'plan_harmonize', 'chat_title')
  ),
  constraint background_jobs_status_check check (
    status in ('pending', 'running', 'success', 'error')
  )
);

create index if not exists background_jobs_user_status_idx
  on public.background_jobs (user_id, status, created_at desc);

create index if not exists background_jobs_pending_idx
  on public.background_jobs (status, created_at)
  where status in ('pending', 'running');

alter table public.background_jobs enable row level security;

create policy background_jobs_all_own on public.background_jobs
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
