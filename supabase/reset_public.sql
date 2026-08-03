-- RESET środowiska goat — uruchom RĘCZNIE w Supabase SQL Editor PRZED świeżym 0001+0002.
-- NIE jest częścią numerowanej historii migracji (świadomie — unikamy auto-wipe przy db push).
-- UWAGA: kasuje WSZYSTKIE tabele/dane w schemacie public + app_private oraz triggery na auth.users.
-- Nie usuwa użytkowników auth.users (konta zostają; profiles i reszta public znikają).

begin;

drop schema if exists app_private cascade;

-- Triggery PRZED funkcjami (inaczej 2BP01: function depends on trigger)
drop trigger if exists on_auth_user_created on auth.users;
drop trigger if exists trg_persona_limit on public.personas;
drop trigger if exists trg_guard_persona_constraints on public.personas;
drop trigger if exists trg_guard_profile_privileged on public.profiles;

drop function if exists public.handle_new_user();
drop function if exists public.enforce_persona_limit();
drop function if exists public.guard_persona_constraints();
drop function if exists public.guard_profile_privileged_columns();

drop table if exists public.admin_audit_log cascade;
drop table if exists public.moderation_events cascade;
drop table if exists public.usage_limits cascade;
drop table if exists public.plan_generation_job_personas cascade;
drop table if exists public.plan_generation_jobs cascade;
drop table if exists public.plan_items cascade;
drop table if exists public.plans cascade;
drop table if exists public.results cascade;
drop table if exists public.chat_messages cascade;
drop table if exists public.chat_sessions cascade;
drop table if exists public.user_profile cascade;
drop table if exists public.personas cascade;
drop table if exists public.exercises cascade;
drop table if exists public.allowed_metrics cascade;
drop table if exists public.plan_templates cascade;
drop table if exists public.persona_templates cascade;
drop table if exists public.profiles cascade;

-- Historia migracji CLI (jeśli używasz supabase db push) — wyczyść, żeby 0001/0002 poszły od zera:
-- delete from supabase_migrations.schema_migrations;

commit;
