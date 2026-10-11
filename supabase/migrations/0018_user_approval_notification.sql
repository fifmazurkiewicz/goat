alter table public.profiles add column if not exists approval_notification_status text not null default 'sent';
alter table public.profiles add column if not exists approval_notification_sent_at timestamptz;
alter table public.profiles add column if not exists approval_notification_error text;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  is_bootstrap_admin boolean;
begin
  is_bootstrap_admin := lower(coalesce(new.email, '')) = 'fifmazurkiewicz@gmail.com';
  insert into public.profiles (id, is_admin, is_approved, approval_notification_status)
  values (new.id, is_bootstrap_admin, is_bootstrap_admin, case when is_bootstrap_admin then 'sent' else 'pending' end);
  return new;
end;
$$;
