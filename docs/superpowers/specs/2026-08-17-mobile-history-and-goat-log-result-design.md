# Design: conversation history on mobile + results saving by Goat

**Date:** 2026-08-17
**Status:** accepted (user chose variant C for mobile, A for results)
**Related:** [ADR-6](../../adr/decisions.md#adr-6-log_result-jako-narzędzie-batch-nie-pojedynczy-wpis), [ADR-17](../../adr/decisions.md#adr-17-kierownik-zespołu-goat--koordynacja-sesji-general), [team-lead.md](../../technical/team-lead.md), [frontend.md](../../technical/frontend.md) §4, [2026-08-17-goat-plan-authority-design.md](./2026-08-17-goat-plan-authority-design.md)

|> **Delta:** (1) `/chat` without `:sessionId` on mobile stops being a dead empty state — shows the conversation list; on app entry the user lands in the latest conversation. (2) Goat gets `log_result` with `source_persona_id=NULL`.

## Problem

### P1 — history unavailable on phone

`ChatLayout` on mobile keeps `PersonaSessionDrawer` only in `Sheet` (closed by default), and its only trigger — "Conversation list" hamburger — lives in `ChatHeader`, which only renders for `activeSession`. Going to `/chat` without an ID gives an empty state with no access to history; the user must create a new conversation to see old ones. Desktop doesn't feel this (drawer permanently attached).

### P2 — Goat doesn't save results

`TEAM_LEAD_CHAT_TOOL_NAMES` doesn't contain `log_result`, and `TEAM_LEAD_TURN_BEHAVIOR` says directly "Don't call log_result". The original assumption ([consult_persona spec](./2026-08-16-goat-consult-persona-design.md) §Out of scope): the result will be saved by the trainer called via `consult_persona`. After the amendment of 2026-08-17 ("Goat by default without consult_persona") this path essentially doesn't run — the user reports the workout to Goat, Goat summarizes and asks for confirmation of the save, but doesn't have a way to save.

## Requirements (Given / When / Then)

### GWT-1 — auto-entry into the latest conversation (mobile)

**Given** phone, user has ≥1 conversation
**When** enters `/chat` without `:sessionId` for the first time since opening the app
**Then** is redirected (`replace`) to the newest conversation by `updated_at`
**And** the hamburger of the conversation list is available in the header

### GWT-2 — conversation list as a screen

**Given** phone
**When** the user is on `/chat` without `:sessionId` and auto-entry already happened (or there's nothing to enter)
**Then** sees a full-screen conversation list (`PersonaSessionDrawer`) with "New conversation"
**And** no further redirect happens (can stay on the list)

### GWT-3 — no conversations

**Given** an account without conversations
**When** the user enters `/chat`
**Then** sees the message "No conversations" + CTA "New conversation", without redirect

### GWT-4 — desktop unchanged

**Given** desktop
**When** the user enters `/chat`
**Then** fixed drawer on the left + empty state "Pick a conversation from the list or start a new one"
**And** no auto-redirect (list is already visible)

### GWT-5 — Goat saves the result

**Given** `general` session, user reports actual result ("today bench 4×8 @45 kg")
**When** Goat calls `log_result` with entries
**Then** entries go to `results` with `source='agent'`, `source_persona_id=NULL`
**And** FE shows "Result" chip, `/results` sees data after invalidation

### GWT-6 — no trainer regression

**Given** trainer (`/slug`, `persona` session, consult backstage)
**When** calls `log_result`
**Then** save with `source_persona_id` = trainer UUID (as today)
**And** the trainer still doesn't have `rebuild_plan` / `consult_persona`

### GWT-7 — Goat doesn't fabricate results

**Given** conversation without a result report (plan, question, motivation)
**When** Goat answers
**Then** doesn't call `log_result` ("only explicitly reported values" rule from ADR-6 / preamble)

## Approach

### Frontend (`ChatLayout`)

```
/chat (mobile, no :sessionId)
├─ sessions.length > 0 && !autoOpenedRef → navigate(latest.id, {replace: true})
└─ otherwise → <PersonaSessionDrawer> full-width (list screen)

/chat (desktop) → as today: 288px drawer + empty state
```

- Newest conversation = max `updated_at` (same data as the list, no new endpoint).
- One-shot guard: `useRef` in `ChatLayout` (shell mount lifetime), not localStorage — after returning to the list in the same session there is no second jump.
- Auto-entry only on mobile; desktop has the list on screen, redirect would be unwanted.
- `sortSessionsByRecency` / `latestSessionId` as pure functions in `lib/chat-session.ts` → testable without render.

### Backend (Goat's `log_result`)

| Element | Change |
|---------|--------|
| `TEAM_LEAD_CHAT_TOOL_NAMES` | + `log_result` |
| `get_team_lead_plan_tools()` | no code change (filters by names) |
| `TEAM_LEAD_TURN_BEHAVIOR` | "Don't call log_result" → "Save the result reported by the user yourself via `log_result`" |
| `ChatOrchestrator._execute_single_tool` | `source_persona_id = None` when `persona.type == "team_lead"` |
| `ResultsService.log_batch_from_agent` | signature `source_persona_id: str \| None` |

Why `NULL`, not a pseudo-persona: `TEAM_LEAD_PERSONA_ID` is `__team_lead__` (not a UUID), and `results.source_persona_id` has FK to `personas(id)` — insert with that string would crash on type/FK. `NULL` is already allowed by the schema (`0001_init.sql:360`) and means "agent without a persona", which for a lead is semantically correct. `/results` UI doesn't require a persona to display an entry.

## Out of scope

- Bottom nav (Chat/Plan/Results) — still deferred.
- Changing result categories / DB migration — none.
- `log_result` for `consult_persona` backstage — works as today.
- Editing/deleting results by Goat (save only).
