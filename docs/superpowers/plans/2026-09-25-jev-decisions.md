# goat Jev Decisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an active but non-authoritative Jev safety/scope gate before goat persists plan patches.

**Architecture:** Add an async Decisions API method to the existing OpenRouter client. The plan-tool write path consumes its result and selects the existing conservative error/confirmation outcome; normal permissions and validation remain unchanged.

**Tech Stack:** Python, FastAPI, httpx, tenacity, pytest.

**Spec:** `docs/superpowers/specs/2026-09-25-jev-decisions-design.md`

## Global Constraints

- Use `typesafe/jev-1.13` through OpenRouter's alpha Decisions API.
- Never bypass tool permissions, plan confirmation, database validation, or safety overlay.
- Failed/uncertain decisions deny automatic writes conservatively.

## Review Focus

- Client failure cannot accidentally permit a write.
- A low-risk response cannot bypass existing authorization.
- Full chat history is not sent or stored.
- A high medical-risk signal results in Polish review copy.
- Retry applies only before any application-visible response.

---

### Task 1: Async decision transport

**Files:** Modify `backend/app/llm/openrouter_client.py`; create `backend/tests/test_jev_decisions.py`.

**Interfaces:** Produce `OpenRouterClient.decide(state: dict[str, Any], questions: dict[str, Any]) -> dict | None`.

- [ ] Write async mocked tests for correct request URL/model, 429 retry, and malformed result returning `None`.
- [ ] Run `cd backend && uv run pytest tests/test_jev_decisions.py -q`; expect failure.
- [ ] Implement a non-streaming POST using the existing client, bounded retry, and typed response validation.
- [ ] Run the focused tests and expect pass.
- [ ] Commit `feat: add goat Jev transport`.

### Task 2: Plan patch gate

**Files:** Modify `backend/app/domain/chat/plan_tools.py`; modify/add `backend/tests/test_tool_validation.py`.

**Interfaces:** Existing plan-upsert result remains a dict; unsafe/uncertain result is a non-persisting Polish review/error result.

- [ ] Write tests for high constraint risk, low confidence, transport failure, and normal path preserving authorization checks.
- [ ] Run the focused test; expect failure.
- [ ] Insert the smallest gate immediately before repository persistence, supplying only user brief, hard constraints, and patch payload.
- [ ] Run focused tests and `uv run pytest tests/test_tool_validation.py -q`.
- [ ] Commit `feat: gate goat plan patches with Jev`.
