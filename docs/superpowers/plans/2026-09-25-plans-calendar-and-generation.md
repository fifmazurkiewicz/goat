# Month-First Plans Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the dual-view Plans screen with a month-first calendar and a guided, scoped day/week/month plan-generation dialog.

**Architecture:** Keep Plans server state in TanStack Query and generation progress in the existing global Zustand store. Extend the existing plan request/job pipeline with a day period, selected persona IDs, and a user brief; render the month and selected-day detail from the same range query. Remove unused Admin diagnostics from the product surface and read endpoints while retaining historical tables.

**Tech Stack:** Vite/React/TypeScript, TanStack Query, shadcn UI, date-fns, FastAPI/Pydantic, async SQL repositories, Supabase migrations, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-25-plans-calendar-and-generation-design.md`

## Global Constraints

- Plans is future-only: do not render completed results inside the Plans detail.
- All active personas are selected by default; Goat remains the coordinator.
- Notes remain editable on the final review step.
- The generation dialog is centered at every breakpoint with a scrollable body and persistent footer.
- Existing job progress, cancellation, idempotency, and partial-success behavior must remain intact.
- Preserve Polish UI copy and existing layout/design-system patterns.
- Do not delete historical moderation/audit rows in this change.

## Review Focus

- A month with no items must still show selectable dates and the single `Ułóż plan` action.
- A day/week/month request must resolve exactly to the requested calendar range, including Monday–Sunday weeks and leap/final month days.
- A user cannot submit no personas or another user’s/inactive persona IDs.
- Closing the dialog must not create a job; an existing active job must still reconcile through the current 409 path.
- A long review note must remain editable and be sent unchanged within the API limit.

### Task 1: Extend the plan generation contract and range semantics

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/api/routers/plans.py`
- Modify: `backend/app/domain/jobs/runner.py`
- Modify: `backend/app/domain/plans/orchestrator.py`
- Modify: `backend/app/domain/chat/plan_tools.py` and `backend/app/domain/chat/tools.py` where period literals are shared
- Modify: `frontend/src/types/api.ts`
- Create: `supabase/migrations/0017_plan_generation_scope.sql` only if durable selected-roster storage is required by the existing job schema
- Test: existing plan router/orchestrator tests plus a focused backend contract test

**Interfaces:**
- `PlanGenerateRequest` becomes `{ period_type: "day" | "week" | "month"; start_date: date; persona_ids: list[str]; user_brief?: str }`.
- The job runner/orchestrator receives the selected roster and brief and uses only that roster.
- `_period_end_date()` returns `start_date` for day, the containing Monday–Sunday range for week, and the containing calendar month for month.

- [ ] Add failing tests for all three range calculations, empty/foreign/inactive persona validation, and request serialization.
- [ ] Run the focused backend tests and confirm failures.
- [ ] Implement the smallest Pydantic/API/repository/orchestrator changes; preserve current active-job and cancellation paths.
- [ ] Add durable job scope fields only where the current background payload/job-persona records cannot already preserve them.
- [ ] Run focused pytest plus backend type/lint checks.
- [ ] Commit: `feat: scope plan generation by period and coaches`.

### Task 2: Build the centered four-step generation dialog

**Files:**
- Create: `frontend/src/components/plans/PlanGenerationDialog.tsx`
- Create: `frontend/src/components/plans/PlanGenerationSteps.tsx` or focused step components if the dialog exceeds one responsibility
- Modify: `frontend/src/hooks/usePlans.ts`
- Modify: `frontend/src/components/plans/GeneratePlanCta.tsx` or replace it with the header action
- Test: `frontend/src/components/plans/PlanGenerationDialog.test.tsx`

**Interfaces:**
- Local draft state: `{ periodType, startDate, personaIds, userBrief, step }`.
- `useGeneratePlan().mutateAsync()` accepts the expanded `GeneratePlanInput` and starts the existing global job store.

- [ ] Write tests for default all-persona selection, day/week/month date controls, no-persona validation, editable review notes, close-without-submit, and exact mutation payload.
- [ ] Run the dialog tests to confirm failures.
- [ ] Implement centered dialog with period/date step, persona step, brief step, and review step; use current UI primitives and accessible labels.
- [ ] Keep the footer fixed inside the dialog and prevent generation while the mutation is pending.
- [ ] Run the dialog tests and frontend lint.
- [ ] Commit: `feat: add guided plan generation dialog`.

### Task 3: Replace Plans with the month-first calendar and selected-day detail

**Files:**
- Modify: `frontend/src/pages/PlansPage.tsx`
- Modify: `frontend/src/components/plans/MonthGridView.tsx`
- Modify: `frontend/src/components/plans/CalendarViewSwitcher.tsx` or remove it if no remaining caller needs it
- Modify: `frontend/src/components/plans/DayPlanDetail.tsx`
- Modify: `frontend/src/components/plans/ActualResultsPanel.tsx` only if deletion is necessary after caller search
- Test: existing month/calendar/day tests plus new `frontend/src/pages/PlansPage.test.tsx`

**Interfaces:**
- Month grid emits `onSelectDate(date)` and renders one presence dot per date with one or more items.
- Plans page owns `month` and `date` URL params, fetches the month range, and scrolls a stable detail anchor after selection.

- [ ] Add tests for one dot regardless of item/persona count, selected-day URL state, scroll target invocation, no completed-results content, and empty day detail.
- [ ] Run focused frontend tests and confirm failures.
- [ ] Remove week agenda/view-toggle state and make month the sole calendar.
- [ ] Render `DayPlanDetail` below the calendar with `Cały plan` default and optional visible persona tabs; do not add swipe-only navigation.
- [ ] Keep generation progress banner and global status behavior.
- [ ] Run frontend tests, lint, and build.
- [ ] Commit: `feat: make Plans month-first with day detail`.

### Task 4: Retire Admin diagnostics and update docs

**Files:**
- Modify: `frontend/src/pages/AdminPage.tsx`
- Modify: `frontend/src/hooks/useAdmin.ts`
- Delete: `frontend/src/components/admin/DeployVersionPanel.tsx`, `ModerationEventsPanel.tsx`, `AuditLogPanel.tsx`
- Modify: `backend/app/api/routers/admin.py`
- Modify: `backend/app/models/schemas.py` imports/usages if diagnostics-only models become unused
- Test: `backend/tests/test_admin_diagnostics.py` and admin frontend tests
- Modify: `docs/technical/frontend.md`, `docs/technical/architecture.md`, `docs/adr/decisions.md`

- [ ] Update tests so deployment-info, moderation-events, and audit-log product endpoints are no longer exposed, while account admin endpoints remain available.
- [ ] Run focused admin tests and confirm failures.
- [ ] Remove UI panels/hooks/read endpoints and diagnostic-only imports. Stop new moderation-event and admin-audit writes, but retain historical tables and repositories so the migration is non-destructive.
- [ ] Update technical docs and ADR with the final route/API behavior.
- [ ] Run backend tests, frontend tests, lint, and build.
- [ ] Commit: `refactor: remove unused admin diagnostics`.

### Task 5: Full verification and delivery

- [ ] Run `cd backend && uv run pytest`.
- [ ] Run `cd backend && uv run ruff check . && uv run ruff format --check .`.
- [ ] Run `cd frontend && npm test`, `npm run lint`, and `npm run build`.
- [ ] Run `git diff --check` and inspect the complete diff for unrelated changes.
- [ ] Apply the Ponytail review: remove any new abstraction or dependency not required by the approved spec.
- [ ] Commit any final fixes, push `main`, and report the commit and test results.

## Self-review

The plan covers every spec requirement: month-only calendar and dots (Task 3),
selected-day detail and optional persona tabs (Task 3), four-step generation and
editable notes (Task 2), day/week/month API scope and durable job context (Task
1), admin removals (Task 4), and verification/documentation (Task 5). No new
dependency is proposed; existing calendar, dialog, query, and job primitives
are reused. Historical data is deliberately retained, avoiding a destructive
migration.
