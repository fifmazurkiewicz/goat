# Working plan: Goat `consult_persona`

**Date:** 2026-08-16  
**Spec:** [docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md](../../docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md)  
**Implementation plan:** [docs/superpowers/plans/2026-08-16-goat-consult-persona.md](../../docs/superpowers/plans/2026-08-16-goat-consult-persona.md)

## Decisions

| Date | Decision | Why |
|------|---------|-----|
| 2026-08-16 | Variant B: in `general` without `/slug` only Goat speaks; expert via tool calling `consult_persona` | Auto-routing speakers breaks the feeling (motor → dietitian). |
| 2026-08-16 | UX status: "Goat is consulting with {persona}…" | User acceptance. |
| 2026-08-16 | Roundtable = N consults + **one** Goat bubble | Consistent with "I'm talking to the lead". |
| 2026-08-16 | Roster = active personas **of this user** (including `custom`); hint without hardcoded motor | User creates their own personas — tool is not limited to dietitian/motor. |
| 2026-08-16 | Cap 5 `consult_persona` / turn | Max 5 personas in the product. |
| 2026-08-17 | Default **without** consult — only when a detail is needed; plan/correction → `rebuild_plan` itself | Free responses; Goat was consulting simple things. |
| 2026-08-17 | `rebuild_plan.user_brief` + role exclusion from brief (e.g. no badminton → skip `badminton_coach`) | Rebuilds ignored "no badminton"; plan came back with badminton. |
| 2026-08-17 | FE initial status: "Goat is preparing a response…" (not "agreeing with the team") | Old copy from the multi-speaker era was confusing while waiting. |

## Status

**Implemented** (2026-08-16): schema, orchestrator, FE chips, cleanup of relay/classifier, docs/ADR.  
**Delta 2026-08-17:** fewer consults + `user_brief` in plan rebuild + FE status.
