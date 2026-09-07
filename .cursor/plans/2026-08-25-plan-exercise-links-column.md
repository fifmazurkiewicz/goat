# Plan exercise links — correct column + richer matcher

**Goal:** Clicking an exercise name in a plan opens `/exercises/:slug`.

**Root cause:** `PlanItemTable` always matched column 0. Motor coach tables put **Dzień** first and **Ćwiczenie** second, so names never linked.

**Decisions (2026-08-25):**
- Detect exercise column via header words `ćwiczenie` / `exercise` (`findExerciseColumnIndex`); fallback column 0.
- Matcher also splits `lub`/`or`/`/` alternatives and uses bag-of-words when tokens are interleaved (e.g. `Calf raise 2-leg`).
- No schema/API change — FE only.

## GWT

- Given columns `["Dzień (P/P/L)", "Ćwiczenie", …]` and a catalog hit in Ćwiczenie, when the plan table renders, Then that cell is a `Link` to `/exercises/:slug` and Day is not.
- Given cell `… LUB kettlebell swing …`, when matching, Then `kettlebell-swing` wins if in catalog.

## Tasks

1. `findExerciseColumnIndex` + matcher candidates/tests — done
2. Wire `PlanItemTable` — done
3. Docs delta `frontend.md` — done
