-- RESET of goat environment — run MANUALLY in Supabase SQL Editor BEFORE a fresh 0001+0002.
-- NOT part of the numbered migration history (deliberately — we avoid auto-wipe on db push).
-- WARNING: drops ALL tables/data in the public + app_private schemas and triggers on auth.users.
-- Does not delete auth.users (accounts remain; profiles and the rest of public disappear).

begin;

drop schema if exists app_private cascade;

-- Triggers BEFORE functions (otherwise 2BP01: function depends on trigger)
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

-- CLI migration history (if you use supabase db push) — clear it so 0001/0002 start from scratch:
-- delete from supabase_migrations.schema_migrations;

commit;