-- ADR-25: optional ordered row [{label, value}] keyed by the logging persona's plan columns
-- (`resolve_persona_columns`). Nullable — results without it keep working; no RLS change.
alter table public.results add column if not exists details jsonb;

comment on column public.results.details is
  'Optional ordered row [{label, value}] keyed by the logging persona''s plan columns (ADR-25).';
