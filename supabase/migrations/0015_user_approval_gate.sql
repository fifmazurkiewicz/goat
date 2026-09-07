-- User approval gate (ADR-22).
-- Existing profiles stay usable (grandfather true). New inserts default false
-- unless handle_new_user / ProfilesRepo.ensure sets true for the admin email.

alter table public.profiles
  add column if not exists is_approved boolean not null default true;

alter table public.profiles
  alter column is_approved set default false;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  is_bootstrap_admin boolean;
begin
  is_bootstrap_admin := lower(coalesce(new.email, '')) = 'fmazurkiewicz@gmail.com';
  insert into public.profiles (id, is_admin, is_approved)
  values (new.id, is_bootstrap_admin, is_bootstrap_admin);
  return new;
end;
$$;

create or replace function public.guard_profile_privileged_columns()
returns trigger
language plpgsql
as $$
begin
  if current_setting('role', true) in ('authenticated', 'anon') then
    if tg_op = 'INSERT' then
      new.is_admin := false;
      new.is_approved := false;
    else
      new.is_admin := old.is_admin;
      new.is_approved := old.is_approved;
      new.max_active_personas := old.max_active_personas;
      new.usage_budget_usd := old.usage_budget_usd;
    end if;
  end if;
  return new;
end;
$$;
