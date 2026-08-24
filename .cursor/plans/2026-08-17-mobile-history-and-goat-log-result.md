# Working plan: conversation history on mobile + `log_result` for Goat

**Date:** 2026-08-17
**Spec:** [docs/superpowers/specs/2026-08-17-mobile-history-and-goat-log-result-design.md](../../docs/superpowers/specs/2026-08-17-mobile-history-and-goat-log-result-design.md)

## Problem (user report)

1. On phone, entering `/chat` (without `:sessionId`) shows an empty state "Pick a conversation from the list or start a new one." The conversation list lives only in a closed `Sheet`, and the only trigger (hamburger) is in `ChatHeader`, rendered only when there is an active session → the user must click "New conversation" to get the hamburger and see history.
2. Goat in chat cannot save reported results to the database — `log_result` is consciously disabled for `team_lead` (`TEAM_LEAD_CHAT_TOOL_NAMES`, prompt "Don't call log_result"), and `consult_persona` after the 2026-08-17 change is rarely called, so nobody saves.

## Decisions

| Date | Decision | Why |
|------|---------|-----|
| 2026-08-17 | Mobile variant **C**: `/chat` without session = full-screen conversation list **and** auto-entry into the latest conversation on startup | User's choice; messenger pattern (list ↔ thread) + quick return to conversation |
| 2026-08-17 | Auto-entry only once per app entry and only on `/chat` without `:sessionId`; does not overwrite manual return to the list | Otherwise the user couldn't stay on the list (redirect-loop UX) |
| 2026-08-17 | Results variant **A**: Goat gets `log_result` | Goat already has the final voice over the plan; no right to save results = inconsistency (user reports workout to Goat, not trainer) |
| 2026-08-17 | `source_persona_id = NULL` for Goat's entries | `TEAM_LEAD_PERSONA_ID` = `__team_lead__` (not a UUID); `results.source_persona_id` column is nullable with FK to `personas` |
| 2026-08-17 | ADR-6/ADR-17 amendment in docs (not a new ADR) | Changing the tool boundary of an existing role, not a new architectural decision |

## Given / When / Then

- Given a phone and existing conversations, When the user enters `/chat` without `:sessionId` for the first time in the browser session, Then they land in the most recently updated conversation (without clicking "New conversation").
- Given phone, When the user returns from a conversation to `/chat` (e.g. after deleting the session or via navigation), Then they see the full-screen conversation list with "New conversation", without another auto-redirect.
- Given no conversations at all, When the user enters `/chat`, Then they see an empty state with CTA "New conversation" (without redirect).
- Given desktop, When the user enters `/chat`, Then behavior as today (fixed drawer + empty state), without auto-redirect.
- Given `general` session and the user reports a workout result to Goat, When Goat calls `log_result`, Then entries go to `results` with `source='agent'` and `source_persona_id=NULL`, and the FE shows the "Result" chip.
- Given trainer (slash/1:1), When calls `log_result`, Then save as today with `source_persona_id` = their UUID (no regression).

## Status

In progress (2026-08-17).
