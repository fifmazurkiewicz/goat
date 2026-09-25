-- Allow one-day plans from the Plans generation dialog.
alter table public.plans drop constraint if exists period_type_check;
alter table public.plans
  add constraint period_type_check check (period_type in ('day', 'week', 'month'));
