# Plan roboczy: Goat `consult_persona`

**Data:** 2026-08-16  
**Spec:** [docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md](../../docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md)  
**Plan implementacji:** [docs/superpowers/plans/2026-08-16-goat-consult-persona.md](../../docs/superpowers/plans/2026-08-16-goat-consult-persona.md)

## Decyzje

| Data | Decyzja | Dlaczego |
|------|---------|----------|
| 2026-08-16 | Wariant B: w `general` bez `/slug` mówi wyłącznie Goat; ekspert przez tool calling `consult_persona` | Auto-routing speakerów psuje feeling (motoryka → dietetyk). |
| 2026-08-16 | Status UX: „Goat konsultuje z {persona}…” | Akceptacja usera. |
| 2026-08-16 | Roundtable = N consultów + **jeden** bubble Goata | Spójne z „rozmawiam z kierownikiem”. |
| 2026-08-16 | Roster = aktywne persony **tego usera** (w tym `custom`); hint bez hardcodu motoryki | User tworzy własne persony — tool nie jest ograniczony do dietetyk/motoryka. |
| 2026-08-16 | Cap 5 `consult_persona` / turę | Max 5 person w produkcie. |
| 2026-08-17 | Domyślnie **bez** consult — tylko gdy potrzeba szczegółu; plan/korekta → sam `rebuild_plan` | Wolne odpowiedzi; Goat konsultował proste rzeczy. |
| 2026-08-17 | `rebuild_plan.user_brief` + wykluczenie ról z briefu (np. bez badmintona → skip `badminton_coach`) | Przebudowy ignorowały „bez badmintona”; plan wracał z badmintonem. |
| 2026-08-17 | Status startowy FE: „Goat przygotowuje odpowiedź…” (nie „uzgadnia z zespołem”) | Stary copy z ery multi-speaker mylił przy czekaniu. |

## Status

**Wdrożone** (2026-08-16): schema, orchestrator, FE chipy, cleanup relay/klasyfikatora, docs/ADR.  
**Delta 2026-08-17:** rzadziej consult + `user_brief` w przebudowie planu + status FE.
