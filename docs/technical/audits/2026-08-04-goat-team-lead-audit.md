# Audit: Goat (Team Lead) — 2026-08-04

**Scope:** `general` session, multi-persona coordination, plan operations, SSE, role boundaries.  
**References:** [ADR-17](../adr/decisions.md#adr-17-kierownik-zespołu-goat--koordynacja-sesji-general), [team-lead.md](../team-lead.md).

## Audit metadata

| Field | Value |
|-------|-------|
| Date performed | 2026-08-04 |
| Environment | code review (local) |
| Performer | agent team (architecture, AI/Python, frontend, docs) |
| Required migrations | `0008_background_jobs`, `0009_persona_role_boundaries`, `0010_drop_personas_chat_model` |

## Verdict

**Pass with notes (P1/P2)** — happy path works; documentation and tests completed in this session. UX trade-offs and routing technical debt remain.

---

## 1. What works well

1. **Role split** — Goat has exclusively `get_plan` + `rebuild_plan`; trainers without `rebuild_plan`.
2. **Visibility in UI** — "Goat · Team Lead" label on plan operations (`persona_id=null` in DB/SSE).
3. **Inter-trainer coordination** — lead's brief + `prior_summaries` in a single turn.
4. **Deterministic bypass** — slash/multi-slash and 1 persona bypass the LLM consultation.
5. **Role boundaries** — `persona_scope.py` + migration `0009` in all template safety.

---

## 2. Risks and gaps

| # | Description | Severity | Status |
|---|-------------|----------|--------|
| 1 | **Multi-slash + plan-only** — `/dietitian /trainer build a plan` → only Goat, trainers skipped despite slashes. Conscious trade-off (plan = Goat), but may confuse the user. | Medium | Documented in [team-lead.md](../team-lead.md) |
| 2 | **Double LLM cost** with plan-only | Medium | **Done** — `build_plan_only_consultation` skips the consultation LLM |
| 3 | **Plan heuristics** — substring matching; risk of false positive/negative. | Medium | Tests in `test_team_lead.py` |
| 4 | **`ChatRoutingService` dead code** | Medium | **Done** — deprecated in `routing.py` |
| 5 | **Consultation fallback** — LLM error → first persona, not "last responding" (ADR-13). | Medium | P2 |
| 6 | **Retry not idempotent** — re-`rebuild_plan` on stream retry. | Medium | Documented |
| 7 | **Persona session + plan** — no `rebuild_plan` in 1:1 chat. | Low | Documented in team-lead.md |
| 8 | **`invoked_via=team_lead`** mapped to `auto_routed` in DB. | Low | Observability |

---

## 3. Manual verification checklist

### Backend — lead flow

- [ ] `TeamLeadService.plan_consultation` — LLM picks 1..N personas (≥2 active personas)
- [ ] `/slug` bypass — deterministic selection
- [ ] Multi-slash bypass — order = order of slashes
- [ ] 1 active persona — without lead LLM
- [ ] `team_phase`: `planning` → `delegating`
- [ ] `team_status` with `consultation.status_message`

### Backend — plan path (Goat visible)

- [ ] "Generate a harmonized plan for August" → only Goat, without dietitian
- [ ] "Build a plan and what to eat" → Goat + trainers
- [ ] Goat doesn't have `log_result` / `update_user_profile`
- [ ] Trainers don't call `rebuild_plan` after `[LEAD'S NOTE]`
- [ ] Goat message: `persona_id=NULL`

### Frontend

- [ ] Header "Goat · Team Lead" in history and streaming
- [ ] Status "Goat is analyzing…" before tokens
- [ ] Trainers still have `Name · Role` label

### Automated tests (2026-08-04)

- [x] `backend/tests/test_team_lead.py`
- [x] `backend/tests/test_orchestrator_team_lead.py`
- [x] `backend/tests/test_chat_tools_schema.py`
- [x] `backend/tests/test_persona_scope.py`
- [x] `frontend/src/lib/team-lead.test.ts`
- [x] `frontend/src/components/chat/MessageList.test.tsx`
- [x] `frontend/src/lib/sse.test.ts` — Goat `persona_id: null`

---

## 4. Follow-up decisions (P2)

1. ~~Skip `plan_consultation` LLM when `is_plan_coordination_only`~~ — done (`build_plan_only_consultation`).
2. ~~Deprecate `ChatRoutingService`~~ — done (`DeprecationWarning`).
3. Restore fallback `get_last_responding_persona` — done in `TeamLeadService`.
4. `rebuild_plan` idempotency guard on retry (active job check).

---

## 5. Audit team

| Role | Scope | Result |
|------|-------|--------|
| Lead AI / Python | `team_lead.py`, orchestrator, tools | Pass + 8 risks |
| Lead Architect | ADR-17, SSE, edge cases | Pass + docs drift |
| Lead Frontend | Labels, streaming, SSE types | Pass + nullable types |
| Documentation Architect | Plan docs, checklist | team-lead.md, ADR-17 |
