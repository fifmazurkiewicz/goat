-- Katalog ćwiczeń: przygotowanie pod import free-exercise-db (yuhonas/free-exercise-db, Unlicense).
-- Plan: .cursor/plans/2026-08-23-exercise-catalog-import.md; ADR-14 (nowelizacja w docs/adr/decisions.md).
--
-- Uruchamiać PRZED importem/seedem 0013 — importowane rekordy mają common_mistakes = NULL
-- (dataset źródłowy nie ma tej treści; nie zmyślamy porad technicznych).
--
-- Idempotentne: można uruchomić wielokrotnie (re-init cloud przez SQL Editor).

-- "Częste błędy" tylko dla ręcznie kuratorowanych wpisów; importowane mają NULL.
alter table public.exercises alter column common_mistakes drop not null;

-- Provenance treści + ochrona ręcznych wpisów przy re-importach.
alter table public.exercises add column if not exists source text not null default 'manual';

-- Oryginalna angielska nazwa (import) — `name` trzyma polskie tłumaczenie LLM;
-- name_en służy dopasowaniu klikalnych linków z planów do katalogu.
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

-- Decyzja usera 2026-08-23: EN odpowiedniki z datasetu zastępują ręczne PL wpisy
-- (przysiad ze sztangą / wyciskanie leżąc / martwy ciąg → Barbell_Squat / Bench_Press / Deadlift).
-- Wpisy badminton_coach pozostają. Idempotentne: usuwa tylko te 3 slugs, tylko gdy są 'manual'.
delete from public.exercises
where source = 'manual'
  and slug in ('przysiad-ze-sztanga', 'wyciskanie-sztangi-lezac', 'martwy-ciag');
