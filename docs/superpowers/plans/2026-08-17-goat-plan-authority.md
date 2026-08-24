# Goat plan authority — Implementation Plan

> **For agentic workers:** TDD per task. Spec: `docs/superpowers/specs/2026-08-17-goat-plan-authority-design.md`

**Goal:** Goat has the final voice over the plan — `upsert_plan_items` in chat + pipeline harmonization as Goat (+ `user_brief` enforcement).

**Architecture:** ADR-2 without changing the order. Personas sketch; Goat patches/removes. FE shows Goat's row in progress.

**Tech Stack:** FastAPI, OpenRouter planner, React/Vite Plans UI

## Global Constraints

- Personas can still `upsert_plan_items` (their own only).
- Goat: `upsert` on any active persona (`persona_id` required in entry).
- No DB migration if FE heuristic is enough.
- PL copy: `Goat · Team Lead`

### Task 1: Tools — Goat has upsert
### Task 2: Harmonization Goat + brief delete
### Task 3: FE progress
### Task 4: Docs + verify + push
