# Import free-exercise-db do katalogu ćwiczeń (ADR-14)

Data: 2026-08-23. Źródło analizy: branch `claude/opengym-feature-analysis-chh59m`
(draft `docs/technical/exercise-catalog-free-exercise-db.md`) + weryfikacja datasetu
skryptem + recenzje: frontend ([Lead Frontend Developer](3ae762e3-2257-446b-8af5-8eb46a3a7216)),
backend/architecture ([Lead Architect](759f935a-3474-4d5e-87be-8a7ccf5c8dc7)).

## Cel

Rozbudowa katalogu ćwiczeń (obecnie 5 ręcznych wpisów) o ~868 pozycji z
`yuhonas/free-exercise-db` (**Unlicense** — domena publiczna, bez atrybucji),
ze zdjęciami w Supabase Storage. Zero ryzyka licencyjnego (w przeciwieństwie do
wcześniejszego pomysłu hasaneyldrm — skip z 2026-08-22 pozostaje aktualny).

## Fakty o datasecie (zmierzone, nie szacowane)

- `dist/exercises.json`: **873 rekordy**, każdy ma **dokładnie 2 zdjęcia** (`exercises/<Id>/0.jpg`, `1.jpg`), 38–73 KB/szt. → **~95–105 MB** całości.
- **5 rekordów bez `instructions`** → pomijane: Iron_Cross, One-Arm_Kettlebell_Swings, Push_Press, Side_Bridge, Side_Jackknife → import **868**.
- level: beginner 523 / intermediate 293 / expert 57 (→ `advanced`). category: 7 wartości; primaryMuscles: 17 wartości.
- slugify(id): **873 unikalnych slugów, zero kolizji** z seedem 0002.
- instrukcje: mean 652 znaków → payload listy ~0,7 MB surowego JSON-a.
- zdjęcia głównie **850×567 (3:2)** — obecny grid 16:9 tnie ~16% kadru.

## Decyzje (user potwierdził 2026-08-23)

1. **Duplikaty EN/PL:** usuwamy 3 ręczne PL odpowiedniki motor_coach (`przysiad-ze-sztanga`,
   `wyciskanie-sztangi-lezac`, `martwy-ciag`) — zostają EN odpowiedniki z datasetu
   (`Barbell_Squat`, `Bench_Press`, `Deadlift`). Wpisy `badminton_coach` nietknięte.
   Usunięcie idzie w migracji DDL (idempotentne `DELETE ... WHERE slug IN (...) AND source='manual'`),
   nie w seedzie.
2. **Filtr kategorii UI:** Select z grupowaniem (Partie mięśniowe / Typ treningu), nie chipy overflow-x.
3. **Język — NOWELIZACJA (2026-08-23, decyzja usera): pełne tłumaczenie PL przez LLM**
   (nazwa + krótki opis + kroki wykonania dla 868 ćwiczeń; oryginał EN w `name_en`).
   Generacja offline przy tworzeniu seeda (subagenci w sesji, docelowo
   `scripts/translate_exercises.py` przez OpenRouter), wynik w migracji `0013` — zero LLM w runtime.
4. **Szczegóły ćwiczenia: strona `/exercises/:slug` wszędzie** (decyzja usera) — karta w katalogu
   i nazwa ćwiczenia w wygenerowanym planie to linki; dialog usunięty. Matcher:
   `frontend/src/lib/exercise-matcher.ts` (normalizacja PL/EN, fallback contains).
5. **Architektura importu:** skrypt = **generator SQL-seeda**, nigdy klient bazy (rozstrzygnięta
   sprzeczność draftu §3↔§10). Artefakt w repo = jedyna prawda; re-init cloud przez SQL Editor działa bez zmian.

## Zadania

### 1. Migracja `0012_exercise_catalog_source_nullable.sql` (DDL, idempotentna)

- `ALTER TABLE exercises ALTER COLUMN common_mistakes DROP NOT NULL;`
- `ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'manual'` + CHECK `('manual','free_exercise_db')` przez `DO $$` block.
- Idempotentne `DELETE` 3 duplikatów PL (patrz wyżej).

### 2. Skrypt `scripts/import_free_exercise_db.py` (+ nowa konwencja `scripts/`)

Kroki: pobranie JSON z pinem SHA commitu datasetu → transform offline (skip pustych instrukcji,
mapowanie pól wg draftu §4, słownik PL jako stały dict, sort po slug deterministyczny)
→ upload zdjęć tylko przy fladze `--upload-photos` (httpx, Storage REST,
`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` z env — **bez supabase-py**, zgodnie z regułą backendu)
→ generacja `supabase/migrations/0013_exercise_catalog_seed_free_exercise_db.sql`
(chunked multi-row INSERT ~100 wierszy/statement, `ON CONFLICT (slug) DO NOTHING`,
`source='free_exercise_db'`, `photo_path` = publiczny URL Storage).
Bez dostępu do bazy — `DATABASE_URL` niewymagany.

### 3. Backend

- `ExerciseRow.common_mistakes: str | None`, `ExerciseOut.common_mistakes: str | None = None`.
- `GZipMiddleware` jako ostatni middleware (minimum_size ~1000) + smoke test streamu SSE po deployu.
- Test kontraktowy (wzorzec `test_chat_messages_contract.py`): repo z `common_mistakes=None` → GET /exercises 200 z `"common_mistakes": null`.

### 4. Frontend

- `types/api.ts`: `common_mistakes: string | null`; usunięcie fantomowego `created_at`.
- `ExerciseDetailDialog.tsx`: sekcja „Częste błędy” warunkowo **razem z Separatorem**.
- `ExerciseGrid.tsx` + dialog: `loading="lazy"` + `decoding="async"` na `<img>`; ratio `3/2` zamiast 16:9.
- `ExerciseCatalog.tsx`: `useDeferredValue(query)`; opis pod nagłówkiem o źródle EN.
- `ExerciseSearchBar.tsx`: chipy → Select z grupowaniem (mięśnie/trening); placeholder „np. squat, bench press”.

### 5. Re-import (procedura)

`DELETE FROM exercises WHERE source='free_exercise_db';` → rerun `0013`. Ręczne wpisy nietykalne.
Nagłówek wygenerowanego pliku dokumentuje procedurę + pin SHA datasetu.

## Poza zakresem v1 (LATER)

Split endpoint lista/detale, wirtualizacja/paginacja, galeria 2 zdjęć, tłumaczenie treści PL (v2 OpenRouter),
filtr `GET /exercises?source=`, kolumny equipment/force/mechanic/secondaryMuscles.

## Docs delta (przy implementacji)

| Dokument | Zmiana |
|---|---|
| `docs/adr/decisions.md` ADR-14 | nowelizacja: nullable, `source`, skala ~870, import skrypt→seed, duplikaty EN/PL świadome |
| `docs/technical/database-schema.md` | `common_mistakes` nullable, `source`, skala tabeli |
| `docs/technical/frontend.md` §7a | warunkowe błędy, lazy img, Select kategorii, koniec „kilkudziesięciu pozycji" |
| `docs/technical/cloud-setup.md` | 0012+0013 w sekwencji re-init; bucket `exercise-photos` (public read, upload tylko service role) |
| `docs/technical/local-setup.md` | jak odpalić import lokalnie |
| `backend/.env.example` | odkomentować `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` z notą o skrypcie (placeholdery) |
| Draft spec na branchu | usunąć sprzeczność §3↔§10, dopisać decyzje |

## Definition of Done

Backend: `pytest` + `ruff check` + `mypy` zielone; frontend: `npm run build` (+ lint per AGENTS/CI);
wizualna weryfikacja `/settings` po imporcie lokalnym; test kontraktowy dla `common_mistakes=null`.
