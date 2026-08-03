-- Jednorazowo w SQL Editor (bez pełnego wipe), gdy konto już istnieje:
-- ustawia is_admin=true TYLKO dla fmazurkiewicz@gmail.com, resztę na false.
-- Wymaga istniejących wierszy w profiles (trigger przy rejestracji).

update public.profiles p
set is_admin = (lower(coalesce(u.email, '')) = 'fmazurkiewicz@gmail.com')
from auth.users u
where u.id = p.id;

-- Jeśli po wipe brakuje wiersza profilu dla zalogowanego usera:
insert into public.profiles (id, is_admin)
select
  u.id,
  (lower(coalesce(u.email, '')) = 'fmazurkiewicz@gmail.com')
from auth.users u
on conflict (id) do update
  set is_admin = excluded.is_admin;
