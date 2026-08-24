# Import free-exercise-db into exercise catalog (ADR-14)

Date: 2026-08-23. Analysis source: branch `claude/opengym-feature-analysis-chh59m`
(draft `docs/technical/exercise-catalog-free-exercise-db.md`) + dataset verification
with a script + reviews: frontend ([Lead Frontend Developer](3ae762e3-2257-446b-8af5-8eb46a3a7216)),
backend/architecture ([Lead Architect](759f935a-3474-4d5e-87be-8a7ccf5c8dc7)).

## Goal

Expand the exercise catalog (currently 5 manual entries) with ~868 entries from
`yuhonas/free-exercise-db` (**Unlicense** — public domain, no attribution),
with photos in Supabase Storage. Zero license risk (unlike the earlier
hasaneyldrm idea — the 2026-08-22 skip remains current).

## Dataset facts (measured, not estimated)

- `dist/exercises.json`: **873 records**, each with **exactly 2 photos** (`exercises/<Id>/0.jpg`, `1.jpg`), 38–73 KB each → **~95–105 MB** total.
- **5 records without `instructions`** → skipped: Iron_Cross, One-Arm_Kettlebell_Swings, Push_Press, Side_Bridge, Side_Jackknife → import **868**.
- level: beginner 523 / intermediate 293 / expert 57 (→ `advanced`). category: 7 values; primaryMuscles: 17 values.
- slugify(id): **873 unique slugs, zero collisions** with the 0002 seed.
- instructions: mean 652 characters → list payload ~0.7 MB raw JSON.
- photos mainly **850×567 (3:2)** — current 16:9 grid crops ~16% of the frame.

## Decisions (user confirmed 2026-08-23)

1. **EN/PL duplicates:** remove 3 manual PL motor_coach counterparts (`przysiad-ze-sztanga`,
   `wyciskanie-sztangi-lezac`, `martwy-ciag`) — the EN counterparts from the dataset
   stay (`Barbell_Squat`, `Bench_Press`, `Deadlift`). `badminton_coach` entries untouched.
   Removal goes in the DDL migration (idempotent `DELETE ... WHERE slug IN (...) AND source='manual'`),
   not in the seed.
2. **UI category filter:** Select with grouping (Muscle groups / Training type), not overflow-x chips.
3. **Language — AMENDMENT (2026-08-23, user decision): full PL translation via LLM**
   (name + short description + execution steps for 868 exercises; EN original in `name_en`).
   Generated offline when creating the seed (subagents in the session, ultimately
   `scripts/translate_exercises.py` via OpenRouter), result in migration `0013` — zero LLM in runtime.
4. **Exercise details: page `/exercises/:slug` everywhere** (user decision) — the card in the
   catalog and the exercise name in the generated plan are links; dialog removed. Matcher:
   `frontend/src/lib/exercise-matcher.ts` (PL/EN normalization, fallback contains).
5. **Import architecture:** script = **SQL seed generator**, never a DB client (resolving the
   draft §3↔§10 contradiction). The artifact in the repo = the only truth; cloud re-init via SQL Editor works without changes.
6. **Catalog idle (2026-08-24):** empty search shows 3 random exercises
   (new trio on each Settings entry + "Show other" button); full list only after typing a phrase.
   The category narrows the random pool, not a dump of 870 cards.

## Tasks

### 1. Migration `0012_exercise_catalog_source_nullable.sql` (DDL, idempotent)

- `ALTER TABLE exercises ALTER COLUMN common_mistakes DROP NOT NULL;`
- `ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'manual'` + CHECK `('manual','free_exercise_db')` via `DO $$` block.
- Idempotent `DELETE` of 3 PL duplicates (see above).

### 2. Script `scripts/import_free_exercise_db.py` (+ new `scripts/` convention)

Steps: fetch JSON pinned to a dataset commit SHA → offline transform (skip empty instructions,
map fields per draft §4, PL dictionary as a static dict, deterministic slug sort)
→ upload photos only with the `--upload-photos` flag (httpx, Storage REST,
`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` from env — **without supabase-py**, per backend rule)
→ generate `supabase/migrations/0013_exercise_catalog_seed_free_exercise_db.sql`
(chunked multi-row INSERT ~100 rows/statement, `ON CONFLICT (slug) DO NOTHING`,
`source='free_exercise_db'`, `photo_path` = public Storage URL).
No database access — `DATABASE_URL` not required.

### 3. Backend

- `ExerciseRow.common_mistakes: str | None`, `ExerciseOut.common_mistakes: str | None = None`.
- `GZipMiddleware` as the last middleware (minimum_size ~1000) + SSE stream smoke test after deploy.
- Contract test (pattern `test_chat_messages_contract.py`): repo with `common_mistakes=None` → GET /exercises 200 with `"common_mistakes": null`.

### 4. Frontend

- `types/api.ts`: `common_mistakes: string | null`; remove the phantom `created_at`.
- `ExerciseDetailDialog.tsx`: "Common mistakes" section conditionally **with a Separator**.
- `ExerciseGrid.tsx` + dialog: `loading="lazy"` + `decoding="async"` on `<img>`; `3/2` ratio instead of 16:9.
- `ExerciseCatalog.tsx`: `useDeferredValue(query)`; description below header about EN source.
- `ExerciseSearchBar.tsx`: chips → Select with grouping (muscles/training); placeholder "e.g. squat, bench press".

### 5. Re-import (procedure)

`DELETE FROM exercises WHERE source='free_exercise_db';` → rerun `0013`. Manual entries untouched.
The generated file header documents the procedure + dataset SHA pin.

## Out of scope for v1 (LATER)

Split list/detail endpoint, virtualization/pagination, 2-photo gallery, PL content translation (v2 OpenRouter),
`GET /exercises?source=` filter, equipment/force/mechanic/secondaryMuscles columns.

## Docs delta (during implementation)

| Document | Change |
|---|---|
| `docs/adr/decisions.md` ADR-14 | amendment: nullable, `source`, scale ~870, script→seed import, conscious EN/PL duplicates |
| `docs/technical/database-schema.md` | `common_mistakes` nullable, `source`, table scale |
| `docs/technical/frontend.md` §7a | conditional mistakes, lazy img, category Select, end of "few dozen entries" |
| `docs/technical/cloud-setup.md` | 0012+0013 in re-init sequence; bucket `exercise-photos` (public read, service role only upload) |
| `docs/technical/local-setup.md` | how to run import locally |
| `backend/.env.example` | uncomment `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` with a note about the script (placeholders) |
| Spec draft on branch | remove §3↔§10 contradiction, add decisions |

## Definition of Done

Backend: `pytest` + `ruff check` + `mypy` green; frontend: `npm run build` (+ lint per AGENTS/CI);
visual verification of `/settings` after local import; contract test for `common_mistakes=null`.
