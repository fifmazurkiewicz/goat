-- One-off in SQL Editor (without a full wipe) when the account already exists:
-- sets is_admin=true ONLY for fmazurkiewicz@gmail.com, everyone else to false.
-- Requires existing rows in profiles (trigger on signup).

update public.profiles p
set is_admin = (lower(coalesce(u.email, '')) = 'fmazurkiewicz@gmail.com')
from auth.users u
where u.id = p.id;

-- If after a wipe a profile row is missing for a logged-in user:
insert into public.profiles (id, is_admin)
select
  u.id,
  (lower(coalesce(u.email, '')) = 'fmazurkiewicz@gmail.com')
from auth.users u
on conflict (id) do update
  set is_admin = excluded.is_admin;