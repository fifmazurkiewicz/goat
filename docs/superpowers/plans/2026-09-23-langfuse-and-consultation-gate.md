# Langfuse Tracing and Consultation Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fail-open Langfuse Cloud traces and require explicit user selection before Goat consults personas.

**Architecture:** An optional backend observability facade owns the Langfuse SDK and is called by the OpenRouter transport and orchestration boundaries. A session-scoped pending-consultation record authorizes only the following user turn to expose `consult_persona`.

**Tech Stack:** FastAPI, async SQLAlchemy/asyncpg, Pydantic Settings, Langfuse Python SDK, HTTPX, PostgreSQL/Supabase, pytest.

**Spec:** [2026-09-23-langfuse-and-consultation-gate-design.md](../specs/2026-09-23-langfuse-and-consultation-gate-design.md)

## Global Constraints

- Use Langfuse Cloud EU (`https://cloud.langfuse.com`); credentials remain server-only.
- Store full approved production content: prompts, outputs, tool inputs/outputs, profile/results/plan context.
- Tracing fails open: it never delays or fails chat, SSE, plan jobs, or API requests.
- User-facing consultation and validation copy stays Polish.
- No automatic consultation: only an explicit selection from an offered active roster unlocks `consult_persona`.
- Direct `/slug` conversations remain unchanged.

## Review Focus

- Missing credentials and SDK failures preserve product behavior (Task 1).
- A streaming transport failure closes the generation observation without changing normal error handling (Task 2).
- Unknown, inactive, or unoffered personas cannot be authorized (Task 3).
- “All” means only offered active personas (Task 3).
- Expired, superseded, declined, or unrelated follow-up messages cannot unlock consultations (Task 3).

### Task 1: Optional Langfuse facade

**Files:**
- Modify: `backend/pyproject.toml`, `backend/app/core/config.py`, `backend/.env.example`
- Create: `backend/app/observability/__init__.py`, `backend/app/observability/langfuse.py`
- Test: `backend/tests/test_langfuse_observability.py`

**Interfaces:** `get_observability() -> Observability`; `Observability.start_trace`, `start_span`, `start_generation`, and `flush`; returned `ObservationHandle.end(output=None, error=None, metadata=None)`.

- [ ] Write failing tests for disabled observations and a broken SDK client.

```python
def test_disabled_observability_returns_noop_handle(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_enabled", False)
    trace = Observability.from_settings().start_trace(name="chat_turn", input={"text": "hi"}, metadata={})
    assert trace.id is None
    trace.end(output={"text": "ok"})
```

- [ ] Run `cd backend && uv run pytest tests/test_langfuse_observability.py -v`; expect failure because the facade is absent.
- [ ] Run `cd backend && uv add langfuse`; add enabled, public key, secret key, EU base URL, environment, and release settings plus placeholder-only example values.
- [ ] Implement the facade. Catch SDK construction, observation creation/update, and flush exceptions; log only the operation and exception class; return no-op handles when disabled or broken.
- [ ] Re-run the test; expect pass.
- [ ] Commit with `git commit -m "Add fail-open Langfuse observability facade"`.

### Task 2: Trace transport, chat, and plan execution

**Files:**
- Modify: `backend/app/main.py`, `backend/app/llm/openrouter_client.py`
- Modify: `backend/app/domain/chat/orchestrator.py`, `backend/app/domain/jobs/runner.py`, `backend/app/domain/plans/orchestrator.py`
- Test: `backend/tests/test_openrouter_observability.py`, `backend/tests/test_chat_observability.py`, `backend/tests/test_plan_observability.py`

**Interfaces:** root `chat_turn` and `plan_generation` traces; nested `llm_round`, `tool:<name>`, `consult_persona`, coordinator, persona, persistence, and harmonization observations.

- [ ] Write a failing `complete_json` test asserting the fake facade receives full request, response, model, usage, latency, and errors.

```python
@pytest.mark.asyncio
async def test_complete_json_records_request_response_and_usage(fake_observability, respx_mock):
    client = OpenRouterClient(observability=fake_observability)
    result = await client.complete_json(model="model", messages=[{"role": "user", "content": "hello"}], json_schema={})
    assert result == {"answer": "ok"}
    assert fake_observability.generations[0].input["messages"][0]["content"] == "hello"
```

- [ ] Run `cd backend && uv run pytest tests/test_openrouter_observability.py -v`; expect failure.
- [ ] Instrument `stream_chat`, `complete_json`, and `get_models`; create root traces in `run_chat_turn` and the plan job runner; propagate parent handles through model, tool, consultation, coordinator, persona, and harmonization calls; bind trace IDs to structlog; initialize/flush in lifespan.
- [ ] Add fake-facade tests for one chat trace with nested tool/trainer observations and one plan trace with parallel persona children plus terminal status.
- [ ] Run `cd backend && uv run pytest tests/test_openrouter_observability.py tests/test_chat_observability.py tests/test_plan_observability.py -v`; expect pass.
- [ ] Commit with `git commit -m "Trace coaching and planning workflows in Langfuse"`.

### Task 3: Persist persona-consultation authorization

**Files:**
- Create: `supabase/migrations/0016_pending_persona_consultations.sql`, `backend/app/repositories/persona_consultations_repo.py`
- Modify: `backend/app/domain/chat/team_lead.py`, `backend/app/domain/chat/tools.py`, `backend/app/domain/chat/orchestrator.py`
- Test: `backend/tests/test_persona_consultations_repo.py`, `backend/tests/test_team_lead.py`, `backend/tests/test_consult_persona.py`

**Interfaces:** `PendingPersonaConsultation`; repository methods `replace_pending`, `get_active`, `authorize_for_message`, `consume`, `clear`; `resolve_consultation_selection(message, offered_personas) -> ConsultationSelection | None`.

- [ ] Write migration and failing selection tests.

```python
def test_selection_accepts_only_offered_persona():
    assert resolve_consultation_selection("Zapytaj dietetyka", [dietitian, trainer]).persona_ids == [dietitian.id]

def test_selection_rejects_unoffered_persona():
    assert resolve_consultation_selection("Zapytaj motorykę", [dietitian]) is None
```

- [ ] Create the user-owned, RLS-protected table with offered IDs/slugs, assistant message ID, status, expiry, and a partial unique index for one pending row per session.
- [ ] Run `cd backend && uv run pytest tests/test_team_lead.py tests/test_persona_consultations_repo.py -v`; expect failure.
- [ ] Implement normalized offered-name/slug matching, explicit Polish all-personas matching, 24-hour expiry, and atomic supersession. Verify ownership and active roster before authorizing.
- [ ] For the specialist-needed turn, persist only relevant active choices and let Goat ask its question; remove `consult_persona` from that turn. On the next turn, authorize a valid choice before tools are built, restrict the tool to selected IDs, consume it at completion, and clear it on decline/change of topic.
- [ ] Run `cd backend && uv run pytest tests/test_team_lead.py tests/test_consult_persona.py tests/test_persona_consultations_repo.py -v`; expect pass for none, one, all, unknown, stale, decline, and direct slash.
- [ ] Commit with `git commit -m "Require persona selection before Goat consultations"`.

### Task 4: Disclose full Langfuse Cloud processing

**Files:**
- Modify: `backend/app/repositories/privacy_repo.py`, `backend/app/api/routers/privacy.py`
- Modify: `frontend/src/components/privacy/PrivacyConsentGate.tsx`, `frontend/src/components/privacy/PrivacyConsentGate.test.tsx`
- Modify: `docs/technical/ai-pipeline.md`, `docs/technical/configuration.md`, `docs/technical/cloud-setup.md`, `docs/technical/team-lead.md`
- Test: `backend/tests/test_privacy_controls.py`

**Interfaces:** a bumped health-consent notice/version that names Langfuse Cloud full-content observability.

- [ ] Write a failing notice test.

```python
def test_health_consent_notice_discloses_langfuse_cloud_full_content():
    assert "Langfuse Cloud" in HEALTH_CONSENT_NOTICE
    assert "pełną treść" in HEALTH_CONSENT_NOTICE
```

- [ ] Run `cd backend && uv run pytest tests/test_privacy_controls.py -v`; expect failure.
- [ ] Bump consent version; update Polish consent and privacy copy; document EU project, access controls, Langfuse retention, Render variables, and manual trace verification. Preserve withdrawal behavior.
- [ ] Run `cd backend && uv run pytest tests/test_privacy_controls.py -v` and `cd frontend && npm test -- --run src/components/privacy/PrivacyConsentGate.test.tsx && npm run lint && npm run build`; expect pass.
- [ ] Commit with `git commit -m "Disclose Langfuse Cloud trace processing"`.

### Task 5: Full verification and deployment handoff

**Files:**
- Modify: `docs/technical/cloud-setup.md`
- Test: `backend/tests/test_langfuse_observability.py`, `backend/tests/test_consult_persona.py`

- [ ] Add a final fake-facade test proving an authorized single-persona consultation creates one root trace and consults only that selection.
- [ ] Run `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy app/domain app/llm`; expect pass.
- [ ] Run `cd frontend && npm test -- --run && npm run lint && npm run build`; expect pass.
- [ ] Document deployment verification: set Cloud credentials on Render; trace a direct Goat chat, a pending-choice then one-persona consultation, explicit all-personas choice, weekly plan job, and a disabled-tracing chat; inspect complete trace hierarchy/content in Langfuse.
- [ ] Commit with `git commit -m "Verify Langfuse tracing and consultation authorization"`.

## Self-Review

- Tasks 1–2 implement optional full-content tracing; Task 3 implements the authorization gate; Task 4 handles consent; Task 5 validates deployment.
- Each review focus item has an owning test task.
- The facade and consultation interfaces are introduced before their consumers.
