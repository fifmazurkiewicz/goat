-- Exercise catalog: preparation for the free-exercise-db import (yuhonas/free-exercise-db, Unlicense).
-- Plan: .cursor/plans/2026-08-23-exercise-catalog-import.md; ADR-14 (revision in docs/adr/decisions.md).
--
-- Run BEFORE the 0013 import/seed — imported records have common_mistakes = NULL
-- (the source dataset lacks this content; we don't fabricate technical tips).
--
-- Idempotent: can be run multiple times (re-init cloud via SQL Editor).

-- "Common mistakes" only for manually curated entries; imported ones have NULL.
alter table public.exercises alter column common_mistakes drop not null;

-- Content provenance + protection of manual entries on re-imports.
alter table public.exercises add column if not exists source text not null default 'manual';

-- Original English name (import) — `name` holds the Polish LLM translation;
-- name_en is used to match clickable links from plans to the catalog.
alter table public.exercises add column if not exists name_en text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'exercises_source_check' and conrelid = 'public.exercises'::regclass
  ) then
    alter table public.exercises
      add constraint exercises_source_check check (source in ('manual', 'free_exercise_db'));
  end if;
end $$;

-- User decision 2026-08-23: EN equivalents from the dataset replace manual PL entries
-- (barbell squat / bench press / deadlift → Barbell_Squat / Bench_Press / Deadlift).
-- badminton_coach entries remain. Idempotent: deletes only those 3 slugs, and only when source='manual'.
delete from public.exercises
where source = 'manual'
  and slug in ('przysiad-ze-sztanga', 'wyciskanie-sztangi-lezac', 'martwy-ciag');