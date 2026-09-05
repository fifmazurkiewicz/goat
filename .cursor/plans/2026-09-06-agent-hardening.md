# Goat Agent Hardening Implementation Plan

> **For agentic workers:** TDD. Do not adopt Agno Team / A2A. Keep ADR-17 (user hears only Goat).

**Goal:** Plan jobs cancel and resume after Render kill; chat turns do not double-spend; consults are read-only; rebuild_plan needs confirm; usage math is honest; Goat gets a safety overlay.

**Architecture:** Existing SSE aggregator + in-process `background_jobs`. Add cooperative cancel, startup requeue, consult tool allowlist, confirm event, usage reconcile fix.

**Tech Stack:** FastAPI, asyncpg, pytest, Vite React.

## Global Constraints

- Branch `harden-agent-runtime` from `origin/main` only.
- Do not include unrelated dirty files (exercise-matcher WIP).
- English identifiers; Polish SSE/UI copy preserve.
- Do not add Agno/ADK/keep-alive.
- Do not parallelize `consult_persona`.
- `cd backend &&` project test command from AGENTS.md / pyproject must pass.
- Do not push to main unless parent asks; you may push the feature branch.

## Files (from audit)

- `backend/app/domain/plans/orchestrator.py` — cancel check, no success after cancel, delete-after-draft
- `backend/app/api/routers/plans.py` — cancel must register in-process task
- `backend/app/domain/jobs/runner.py` — requeue pending|running on startup
- `backend/app/domain/chat/orchestrator.py` — timeout per round, persist txn, consult tools, rebuild idempotency
- `backend/app/domain/chat/tools.py` / `plan_tools.py`
- `backend/app/domain/usage/service.py` + orchestrator reconcile
- `backend/app/domain/chat/preamble.py` — Goat overlay
- `backend/app/api/routers/chat.py` — timeout / 409
- Tests under `backend/tests/`

---

### Task 1: Plan job cancel + startup requeue

**Given** user cancels a plan job  
**When** `_run` is still going  
**Then** it stops and status stays cancelled/error — never `success`.

**Given** process starts with `pending` or `running` jobs  
**When** `resume_pending_jobs_on_startup`  
**Then** they are requeued (not left `running` forever; do not skip `running`).

- [ ] Failing tests
- [ ] Implement cooperative cancel (reuse `turn_registry` pattern: `job_id → Task`)
- [ ] Commit

### Task 2: Chat turn lifecycle

- Raise Goat connected timeout or timeout per LLM round (not 90s for the whole turn)
- On startup: `turn_in_progress=false` for orphans
- Persist assistant + tool rows of one round in one transaction
- 409 if turn in progress (unless retry/cancel)
- `rebuild_plan` idempotent on retry (return existing job_id)

### Task 3: Consult read-only

Nested `consult_persona` tools = empty or `get_plan` only. Increment consult cap only after success.

### Task 4: Confirm rebuild_plan

SSE event or tool result “Potwierdź przebudowę planu” before enqueue. If too large for FE in this pass: refuse auto rebuild when a job is already in-flight (surface unique index as a tool error) + require the user message to contain an explicit confirm word on the *next* turn. Prefer a small `tool_confirm` if FE already has chip patterns.

### Task 5: Usage reconcile + Goat safety overlay

- Pass the reserved USD into reconcile; do not recompute with `prompt_chars_estimate=0`
- Plan jobs: reconcile after completion
- Goat gets platform red-flag overlay (same text family as trainer templates)

### Task 6: Docs delta

`docs/technical/team-lead.md` + ADR note: consults read-only; cancel semantics.

## Manual tests (Polish UI)

1. **Anulowanie planu** — w zakładce Plany uruchom generowanie, w trakcie kliknij Anuluj. Job zostaje `error` / „Anulowano”, plan nie przechodzi na „gotowy”.
2. **Restart w trakcie joba** — zrestartuj backend przy `pending`/`running`. Po starcie job wraca (nie znika i nie jest tylko „zabity” po 5 min).
3. **Goat + konsultacja > 90 s** — w czacie ogólnym poproś o rzecz wymagającą `consult_persona`. SSE nie urywa się po 90 s; status „Goat konsultuje z …”.
4. **409 / Stop** — wyślij wiadomość, od razu drugą (bez Stop). Powinien być komunikat, że tura już trwa. Stop kończy turę; „Wyślij ponownie” (retry) działa.
5. **Potwierdzenie przebudowy** — napisz „przebuduj plan na tydzień”. Goat / chip: „Potwierdź przebudowę planu”. Napisz „tak” — dopiero wtedy startuje job w Plany. Drugie „przebuduj” przy trwającym jobie nie odpala drugiego pipeline’u.
6. **Konsultacja tylko do odczytu** — Goat woła trenera; trener nie zapisuje wyniku / profilu / pozycji planu w tej konsultacji.
7. **Overlay Goat** — pytanie o leki / czerwone flagi: Goat odmawia jak trenerzy (nie przepisuje leków, kieruje do specjalisty).

## Decisions (2026-09-06 review follow-up)

- Job status `UPDATE` is CAS: `WHERE status IN ('pending','running')`. Plan `ready`/`error` only if that write lands.
- Startup order: `resume_pending` then `resume_orphaned` (never the reverse).
- Live in-process chat turn always 409, including `retry=true`. Retry only for a DB orphan.
- `rebuild_plan` enqueue requires prior `needs_confirm` in history plus user „tak”. Model `confirmed` is ignored.

## Manual tests (after implementation)

Same as the Polish UI list above. After review fixes, also:

8. **Cancel vs finish race** — cancel a nearly-done plan job; it must stay `error`, never flip to ready.
9. **Retry while streaming** — drop the tab mid-turn (SSE gone, backend still working) then tap Resend: expect 409 until the turn finishes or you hit Stop.
10. **Tak without prior confirm** — first message „tak” must not start a rebuild job.
