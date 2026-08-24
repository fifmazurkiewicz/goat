# Plan: Goat consultation visibility + Pull-to-refresh (mobile)

**Date:** 2026-08-22
**Branch:** `feature/discussion`
**Specs:**
- `docs/superpowers/specs/2026-08-22-goat-consult-transparency-design.md` (existing, on branch)
- `docs/superpowers/specs/2026-08-22-pull-to-refresh-design.md` (new)

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Consultations: expandable panel under Goat's message (collapsed by default), live via new SSE event `consult_detail`, history by pairing `tool_calls` ↔ `role='tool'` by `tool_call_id` | Data is already in DB; we don't change the "who speaks" model (ADR-17) |
| D2 | Don't extend the `tool_result` contract — separate `consult_detail` event | The `_tool_result_event_payload` docstring explicitly forbids raw JSON; other consumers won't suddenly get large text |
| D3 | `question` added to the JSON tool response of `_consult_persona` (no DB schema change) | History gets complete data without reading arguments from a separate assistant message |
| D4 | PTR: soft refresh (`invalidateQueries()` globally), touch-only, wrapper in AppShell around `<Outlet />`, 72 px threshold | User chose "everywhere", mobile/touch, without hard reload; one mount point = all screens |
| D5 | Trainer prompt in consultation stays unchanged (option A from the spec) | It's the same text on the basis of which Goat builds the response anyway; potential option B after observing quality |
| D6 | `overscroll-behavior-y: none` on html/body | Disables Chrome Android's native PTR that would collide with the custom indicator |

## Tasks

### A. Backend — consultation visibility

1. **TDD:** test in `backend/tests/test_consult_persona.py`: happy path `_consult_persona` → JSON contains `question`; error → no field.
2. `orchestrator.py::_consult_persona`: add `"question": question` to the `status: ok` return.
3. **TDD:** test: emit `consult_detail` only on ok, payload `{tool_call_id, slug, persona_label, question, answer}`.
4. Pass `user_queue` + `tool_call_id` to `_consult_persona` (new parameters), emit after successful response, alongside the existing `tool_result`. Place: before Goat's synthesis continues.

### B. FE — consultation history

5. **TDD:** `chat-messages.test.ts`: `visibleChatMessages`/new function builds `consultDetails` on Goat's messages with `role='tool'` (pairing by `tool_call_id`, order preserved); malformed JSON skipped; `role='tool'` still invisible as a message.
6. `lib/chat-messages.ts`: extend parsing with consultation extraction (type `ConsultDetail {personaLabel, question, answer}`); result: `ChatMessage & { consultDetails?: ConsultDetail[] }`.
7. Type `ChatMessage` FE: optional field `consultDetails?`.

### C. FE — live consultations

8. **TDD:** SSE types: new event `ChatStreamConsultDetailEvent` in the union.
9. `useChatTurnRunner.ts`: accumulate `consultDetails` per turn analogously to `toolResults`; on turn finalization (`finalizeStreamingTurn`) append to Goat's message in React Query cache.

### D. UI — component

10. **TDD:** `ConsultDetails.test.tsx`: collapsed by default; expand shows question + answer; no render when empty; 2+ consultations = list in order.
11. `components/chat/ConsultDetails.tsx`: list of `<details>` elements under Goat's bubble (style: smaller font, frame, indent — "source preview", not a trainer message). Check primitives in `components/ui`.

### E. Pull-to-refresh

12. `hooks/usePullToRefresh.ts`: pointer events (touch only), scroller detection (parent chain), distance suppression, 72 px threshold, `isRefreshing`.
13. `components/layout/PullToRefresh.tsx`: wrapper with animated indicator (transform translateY), spinner during refresh.
14. `AppShell.tsx`: mount around `<Outlet />`; `onRefresh` = `queryClient.invalidateQueries()`.
15. `index.css`: `overscroll-behavior-y: none` on html/body.
16. **TDD:** hook/wrapper test: GWT-1..6 from the spec (jsdom pointer events).

### F. Docs

17. `docs/technical/team-lead.md`: "Consultation visibility" section + SSE diagram (+`consult_detail`).
18. `docs/technical/ai-pipeline.md` §1a: mention of `consult_detail`.
19. `docs/technical/architecture.md` §3a: `consult_detail` in the SSE events list.
20. `docs/technical/frontend.md`: `ConsultDetails` + PTR section.
21. `AGENTS.md`: facts (consultation visibility; PTR mobile).

### G. Definition of Done

22. Backend: `pytest backend/tests -k "consult or chat"` green.
23. Frontend: `npm run lint && npm run test && npm run build` green.
24. Smoke in the browser (desktop + devtools mobile emulation): consultation visible after expand; PTR works on emulated touch.

## Order

A → B → C → D (consultation vertical), then E (PTR), F at the end as delta-docs. Tests red before each behavior change.
