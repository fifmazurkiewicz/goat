# Goat plan authority — Implementation Plan

> **For agentic workers:** TDD per task. Spec: `docs/superpowers/specs/2026-08-17-goat-plan-authority-design.md`

**Goal:** Goat ma ostateczny głos nad planem — `upsert_plan_items` w czacie + harmonizacja pipeline jako Goat (+ egzekucja `user_brief`).

**Architecture:** ADR-2 bez zmiany kolejności. Persony szkicują; Goat patchuje/usuwa. FE pokazuje wiersz Goata w postępie.

**Tech Stack:** FastAPI, OpenRouter planer, React/Vite Plans UI

## Global Constraints

- Persony nadal mogą `upsert_plan_items` (tylko swoje).
- Goat: `upsert` na dowolną aktywną personę (wymagane `persona_id` w entry).
- Bez migracji DB jeśli da się heurystyką FE.
- PL copy: `Goat · Kierownik Zespołu`

### Task 1: Tools — Goat ma upsert
### Task 2: Harmonizacja Goat + brief delete
### Task 3: FE postęp
### Task 4: Docs + verify + push
