-- Versioned health-data consent, AI disclosure acknowledgement and retention support.
create table public.privacy_consents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  consent_type text not null,
  document_version text not null,
  notice_text text not null,
  notice_sha256 text not null,
  granted_at timestamptz not null default now(),
  withdrawn_at timestamptz,
  created_at timestamptz not null default now(),
  constraint privacy_consent_type_check check (consent_type in ('health_data', 'ai_disclosure'))
);

create unique index privacy_consents_one_active
  on public.privacy_consents (user_id, consent_type)
  where withdrawn_at is null;
create index privacy_consents_user_created_idx
  on public.privacy_consents (user_id, created_at desc);

alter table public.privacy_consents enable row level security;
create policy privacy_consents_select_own on public.privacy_consents
  for select using (user_id = auth.uid());
create policy privacy_consents_insert_own on public.privacy_consents
  for insert with check (user_id = auth.uid());
create policy privacy_consents_update_own on public.privacy_consents
  for update using (user_id = auth.uid()) with check (user_id = auth.uid());

comment on table public.privacy_consents is
  'Append-only consent history. Withdrawal closes an active record; a later grant inserts a new record.';

-- Keep the security audit when an administrator deletes their own account, but
-- remove the direct Auth identifier so the FK cannot block the erasure request.
alter table public.admin_audit_log
  drop constraint if exists admin_audit_log_admin_user_id_fkey;
alter table public.admin_audit_log
  alter column admin_user_id drop not null;
alter table public.admin_audit_log
  add constraint admin_audit_log_admin_user_id_fkey
  foreign key (admin_user_id) references auth.users (id) on delete set null;
