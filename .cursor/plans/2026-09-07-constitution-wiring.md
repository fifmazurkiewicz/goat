# Constitution wiring (in-repo)

**Goal:** Make goat a self-contained constitution clone: rules, ignore, Commands, CI, health contract. Do not change ADR-19 lamp. Do not include exercise-matcher WIP.

## Requirements (Given / When / Then)

**Given** a clone without `~/.cursor/rules`  
**When** Cursor opens this repo  
**Then** Superpowers, spec-driven, deploy standard, secrets, language, Taste, Graft, and terminal rules apply from `.cursor/rules/`.

**Given** `GET /api/health`  
**When** the API is up  
**Then** `200` and `{ "status": "ok", "service": "goat" }`.

**Given** CI on `main` / PR  
**When** frontend tests exist  
**Then** `npm test` runs (not only lint + build). Dependabot and a verified secret scan run too.

## Decisions (2026-09-07)

- Copy constitution rules into `.cursor/rules/` (keep existing `graft.mdc`). Overlay Taste dials: VARIANCE 3 / MOTION 2 / DENSITY 6 (coaching dashboard).
- Keep ADR-19 wake-window lamp; do **not** add ApiPulse keep-alive. Only add `service` on liveness JSON.
- Nested `frontend/AGENTS.md` and `backend/AGENTS.md` hold Commands; root `AGENTS.md` gets Commands + stack above learned facts.
- Secret scan: TruffleHog `--only-verified` in CI (low false-positive).

## Tasks

- [x] Rules + `.cursorignore` + taste overlay
- [x] AGENTS.md Commands + nested AGENTS
- [x] Health JSON `service` (TDD)
- [x] CI `npm test` + Dependabot + secret scan
- [x] `docs/technical/configuration.md` + devops/ADR delta; English `.env.example` comments
