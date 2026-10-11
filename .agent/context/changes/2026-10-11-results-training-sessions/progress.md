# Progress — results training sessions (ADR-25)

Plan: `docs/superpowers/plans/2026-10-11-results-training-sessions.md` · Spec: `docs/superpowers/specs/2026-10-11-results-training-sessions-design.md`
Execution: native (approved 2026-10-11). Migration `0018` is run by the user in Supabase. Target: commit + push to `main`.

| Task | Status |
|---|---|
| 1 Migration + DTOs | done |
| 2 Persist/expose details, log_result | done |
| 3 plan_columns on GET /personas | done |
| 4 Columns prompt block | done |
| 5 Backend gates | done |
| 6 FE types + grouping | done |
| 7 Session list | done |
| 8 Manual entry with columns | done |
| 9 Docs, gates, visual check | done |

Deviation: `PlanItemTable` gained opt-in `hideEmptyCardCells` (session cards were noisy with "—"); plans unchanged.
Evidence: `evidence.md`.
