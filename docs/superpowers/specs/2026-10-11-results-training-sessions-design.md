# Results tab — training sessions with per-persona columns (design)

- **Date:** 2026-10-11
- **Status:** approved in chat, awaiting written-spec review
- **ADR:** ADR-25 (proposed) in `docs/adr/decisions.md`
- **Related:** ADR-6 (`log_result` batch), ADR-9 (`/results` charts), `docs/technical/frontend.md` §6, `docs/technical/ai-pipeline.md` §2, plan columns (`resolve_persona_columns`, `plan_templates.default_columns`)

## 1. Intent

**User said:** the Results tab should show a list of training sessions, each listing exercises with their values (e.g. "dead bug — 3 serie, 10 powtórzeń, 50 kg na stronę"). The structure must be universal: a badminton session has different attributes than a strength session.

**Decisions taken in chat:**

| Question | Decision |
|---|---|
| What happens to current Results content | Category tabs stay; categories backed by a persona with plan columns show a **session list** instead of the chart; diet and other column-less categories keep chart + table |
| What is one session | **One day = one session** (all entries of a category on a `logged_date`) |
| How values are stored | Logged row uses the **same columns as the persona's plan** (`resolve_persona_columns`), stored in a new `results.details` |

**Success criteria:**

1. A strength session reported in chat ("dziś dead bug 3x10, 50 kg na stronę, wiosłowanie 4x8 16 kg") appears on `/results` → Trening as one day card with one row per exercise, using the trainer's plan columns.
2. A badminton session appears with the badminton coach's columns (drill, time, intensity, …) — no code change per persona type; custom personas work through their own columns.
3. Existing results (no `details`) still render; existing charts for diet / body weight / 1RM keep working.

## 2. Data model

Migration `supabase/migrations/0018_result_details.sql`:

```sql
alter table public.results add column details jsonb;
comment on column public.results.details is
  'Optional ordered row [{label, value}] keyed by the logging persona''s plan columns.';
```

Shape (ordered list, not an object — `jsonb` does not preserve object key order and the row must render in plan-column order):

```json
[
  {"label": "Ćwiczenie", "value": "Dead bug"},
  {"label": "Serie", "value": "3"},
  {"label": "Powtórzenia", "value": "10"},
  {"label": "Ciężar (kg)", "value": "50 / stronę"}
]
```

Validation (Pydantic `ResultDetailCell`, shared by manual API and `log_result`):

| Field | Rule |
|---|---|
| list length | 1–12 |
| `label` | trimmed, 1–60 chars, unique within the row |
| `value` | trimmed string, 1–120 chars (numbers are sent as strings; free text like "2×15 min" allowed) |

Unchanged: `metric`, `value`, `unit` stay required. Convention for rows with `details`: `metric` = exercise / drill name (as the user would say it), `value` = the main number (load, or reps for bodyweight work, or minutes for time-based work), `unit` accordingly. Metric outside `allowed_metrics` → `is_custom=true` (existing behavior). Charts keep reading `metric`/`value`.

No RLS change (column on an existing own-rows table). `database-schema.md` gets the new column.

## 3. Backend

1. **Schemas** (`backend/app/models/schemas.py`): add `details: list[ResultDetailCell] | None` to `ResultCreate`, `ResultUpdate`, `ResultOut`, `LogResultEntry`. `ResultOut` must expose it (lesson from the `tool_calls` hotfix — contract test).
2. **Repo / service** (`results_repo.py`, `domain/results/service.py`): persist `details` via `CAST(:details AS jsonb)` (asyncpg pattern); `None` = column untouched on update unless explicitly sent.
3. **Tool schema** (`domain/chat/tools.py` `LOG_RESULT_TOOL_SCHEMA`): optional `details` array of `{label, value}` per entry. Description (Polish, model-facing): fill `details` only for training/session entries, use exactly the labels from the columns block, skip columns the user did not report — never guess values.
4. **Columns in the chat prompt** (`domain/chat/context_builder.py`): new block `build_result_columns_block`:
   - persona chat: `[KOLUMNY WYNIKÓW] Przy log_result wypełniaj details kolumnami: Ćwiczenie | Serie | …` — from `resolve_persona_columns(persona, plan_template)`.
   - Goat (general session): one line per active persona (`{name} ({category}): col | col | …`), so Goat logs under the right persona's columns and sets `source_persona_id` per ADR-6 amendment rules.
   - Columns that are pure planning metadata are still listed; the model omits what was not reported.
5. **Preamble version**: bump only if the preamble text itself changes (it should not; the block lives in the context builder).

## 4. Frontend — `/results`

Component tree (update `docs/technical/frontend.md` §6):

```
ResultsPage (smart) — category tabs (unchanged)
├─ TrainingSessionList (smart) — when the category has a persona with plan columns
│  └─ SessionCard (dumb) — date + persona, rows from `details`
│     ├─ desktop: table, columns = union of labels in that day's rows (first-seen order)
│     └─ mobile (<sm): one line per exercise "**Dead bug** · Serie 3 · Powtórzenia 10 · Ciężar 50 / stronę"
├─ ResultsChart + ResultsTable — other categories (unchanged)
└─ AddResultDialog — persona picker → inputs for that persona's columns (+ metric/value/unit)
```

- Pure grouping in `lib/training-sessions.ts`: results of the category → `{date, personaIds, rows}[]`, newest first. Rows without `details` render as a fallback row `metric value unit` (+ notes).
- Exercise name (first `details` cell, else `metric`) links to `/exercises/:slug` when `exercise-matcher.ts` finds a catalog match.
- Row edit/delete reuse `useUpdateResult` / `useDeleteResult` (edit dialog shows `details` inputs).
- "Has plan columns" = a persona mapped to the category (`personaResultCategory`) exists; column list comes from the persona's resolved columns — exposed as `plan_columns: string[]` on `GET /personas` items (read-only, computed with `resolve_persona_columns`), so the dialog and the session list need no second request.
- Polish UI copy; empty state: "Brak zapisanych sesji — zgłoś trening w czacie albo dodaj go ręcznie."
- Accessibility: semantic `<table>` with `<th scope="col">` on desktop, `<ul>` on mobile; edit buttons with accessible names.

## 5. Out of scope

- Line-by-line plan vs done comparison (the shared column shape makes it a later step).
- Charts computed from `details` values.
- Back-filling `details` for existing results.
- Multiple sessions per day.

## 6. Testing

| Layer | Test |
|---|---|
| Backend | `ResultDetailCell` validation (length, unique labels, trimming); `log_result` round-trip with `details`; manual `POST/PATCH /results` with `details`; contract test that `GET /results` exposes `details`; `build_result_columns_block` for persona and Goat; `GET /personas` exposes `plan_columns` |
| Frontend | `lib/training-sessions.ts` grouping (by day, newest first, union of labels, fallback rows); `SessionCard` renders table / mobile list; `AddResultDialog` builds `details` from persona columns |
| Gates | `uv run pytest`, `ruff check`, `ruff format --check`, `mypy app/domain app/llm`; `npm test`, `npm run lint`, `npm run build` |

## 7. Rollout

1. Run `0018_result_details.sql` in Supabase SQL Editor (prod) and locally before deploying the backend (column is nullable — old backend keeps working).
2. Deploy backend (Render), then frontend (Vercel).
3. Update `AGENTS.md` workspace facts (migration list) and `docs/technical/database-schema.md`, `frontend.md` §6, `ai-pipeline.md` §2.
