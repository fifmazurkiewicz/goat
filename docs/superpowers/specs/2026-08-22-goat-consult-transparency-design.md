# Design: Visibility of Goat's consultations (trainer answers in `consult_persona`)

**Date:** 2026-08-22
**Status:** proposed (for implementation)
**Based on:** [2026-08-16-goat-consult-persona-design.md](./2026-08-16-goat-consult-persona-design.md), [team-lead.md](../../technical/team-lead.md)

## Problem

When Goat calls `consult_persona`, the user only sees the background status ("Goat is consulting with {trainer}…") and the final synthesis by Goat. The full trainer answer (`answer` in the tool response) exists — it's even saved to the database (`insert_tool_message`, `role='tool'`) — but it's never shown to the user: FE explicitly filters `role='tool'` (`frontend/src/lib/chat-messages.ts:12`, test `chat-messages.test.ts:19` "hides role=tool").

The user wants to be able to **peek** at what the consulted trainer actually answered, instead of relying only on Goat's synthesis.

## Goal / scope

Add an **optional, collapsed by default** panel under Goat's message: "See what {trainer} answered" — per consultation, in call order. This covers:

1. **Live** — consultations done in the current turn (SSE).
2. **History** — consultations from previous turns, after reload/opening of the `general` session (`GET /chat/sessions/{id}/messages`).

**We do not change** the ADR-17 foundation: Goat remains the only "speaker" visible by default; the trainer still doesn't have their own bubble message with an avatar as an active conversation participant. What we add is **transparency on demand** (expandable detail), not a change of the "who speaks" model.

## Requirements (Given / When / Then)

### GWT-1 — consultation in current turn is visible on expand

**Given** during its turn Goat calls `consult_persona(slug, question)`
**When** the trainer returns an answer (`status: "ok"`)
**Then** under Goat's final message an expandable element appears with the trainer's label (`persona_label`), **collapsed** by default
**And** on expand the user sees both the **question** Goat asked the trainer and the **full answer** from the trainer
**And** the element doesn't look like a separate trainer message (no avatar/persona header as a "speaker") — it's an attachment to Goat's message

### GWT-2 — multiple consultations in a single turn (roundtable)

**Given** Goat consults several trainers in the same turn (e.g. "let everyone speak")
**When** the turn ends
**Then** under Goat's message a **list** of expandable elements appears, one per consultation, in call order
**And** each has its own trainer label and its own question/answer

### GWT-3 — consultation error creates no attachment

**Given** `consult_persona` returns `{"error": ...}` (bad slug, timeout, limit)
**When** the turn ends
**Then** **no** expandable element appears (the error remains visible only as the existing `tool_result` chip / Goat's message)

### GWT-4 — session history after reload

**Given** the user opens the `general` session again with previous consultations
**When** FE fetches `GET /chat/sessions/{id}/messages`
**Then** Goat messages after which a successful consultation happened have the same expandable element as in live mode (identical content: question + answer + label)
**And** the order and assignment to the correct Goat message is preserved (paired by `tool_call_id`)

### GWT-5 — slash / 1:1 session unchanged

**Given** a `/slug` message or `persona` session
**When** the turn runs
**Then** no consultations, no new UI element (the feature applies only to the Goat + `consult_persona` path)

## Architecture

### Backend — change 1: `question` in tool response `consult_persona`

`backend/app/domain/chat/orchestrator.py`, `_consult_persona` (~line 848-857) already knows `question` (unpacked from arguments), but doesn't put it in the returned JSON. Add the `question` field, so the persisted `tool` message (and SSE event, see below) carries the complete data without needing to read `tool_calls.arguments` separately from the preceding `assistant` message:

```python
return json.dumps(
    {
        "status": "ok",
        "slug": target.slug,
        "persona_label": label,
        "question": question,      # NEW
        "answer": answer.strip(),
    },
    ensure_ascii=False,
)
```

No DB schema change — `chat_messages.content` is already a `text`/`jsonb`-friendly field, consultations are already persisted (`insert_tool_message`, line ~631-638).

### Backend — change 2: new SSE event `consult_detail` (live)

Don't extend the `tool_result` contract (`_tool_result_event_payload`, `orchestrator.py:149`) — its docstring explicitly says "FE contract (tool_name/summary/success) — not raw JSON tool response", this is a conscious decision and other `tool_result` consumers shouldn't suddenly receive a large text. Instead, in `_consult_persona`, **alongside** the existing `tool_result`, emit a dedicated event only when `status == "ok"`:

```python
if user_queue is not None and ok:
    await _emit(
        user_queue,
        "consult_detail",
        {
            "tool_call_id": tool_call_id,   # pass via _consult_persona signature
            "slug": target.slug,
            "persona_label": label,
            "question": question,
            "answer": answer.strip(),
        },
    )
```

Requires passing `tool_call_id` to `_consult_persona` (today only `_run_single_tool`/the loop in `handle_message` knows it, ~line 599-610) — pull through as a parameter.

Place in the stream: **after** this consultation's `tool_result`, before continuing Goat's tokens (synthesis) or the next consultation.

### Backend — no changes

- Limit of 5 consultations/turn — unchanged.
- Persistence — already works (`role='tool'`), only FE currently hides it.
- Moderation — the trainer's answer goes through the same pipeline as today (trainer's system prompt + `safety_prompt`); we don't add a new path of unmoderated content, because Goat already sees this text in context (today he just synthesizes it instead of showing it 1:1).

### Frontend — SSE (live)

`frontend/src/types/chat-stream.ts` — new type:

```ts
export interface ChatStreamConsultDetailEvent {
  type: "consult_detail";
  tool_call_id: string;
  slug: string;
  persona_label: string;
  question: string;
  answer: string;
}
```

Add to the `ChatStreamEvent` union.

`frontend/src/hooks/useChatTurnRunner.ts` — collect `consult_detail` events in a per-turn buffer (e.g. `consultDetails: ChatStreamConsultDetailEvent[]`), similar to the accumulation of `tool_calls`/tokens. On finalizing Goat's message (`done`) attach the collected list to the message object in the store (e.g. `message.consultDetails`), so `MessageBubble` has access to it.

### Frontend — history (reload)

`frontend/src/lib/chat-messages.ts` — today line 12 rejects `role === "tool"` entirely. Change: **don't** render `role='tool'` as a separate message (this doesn't change — still no trainer bubble), but **extract** consultation data from those rows and attach to the preceding `assistant` message (Goat) by `tool_call_id`:

1. Iterate messages in order.
2. For `role='assistant'` with `tool_calls` containing a `consult_persona` call — remember `tool_call_id → assistant.id`.
3. For the next `role='tool'` with that `tool_call_id`, parse `content` as JSON; if it has `status: "ok"` and an `answer` field — build an entry `{persona_label, question, answer}` and append to `consultDetails` of the corresponding Goat message from step 2.
4. `role='tool'` rows still don't go to the rendered message list (as today).

Parsing resilient to errors (`try/catch` → skip entry, don't break the whole history) — same pattern as the rest of the FE tool response parsing.

### Frontend — UI component

New component, e.g. `frontend/src/components/chat/ConsultDetails.tsx`:

- Rendered under the `MessageBubble` body **only** for Goat messages (`persona_id === null`) with non-empty `consultDetails`.
- List of expandable elements (`<details>`/Radix Collapsible/Accordion — use an existing primitive from `components/ui` if present; check `components/ui/accordion.tsx` or similar before writing from scratch).
- **Collapsed** by default.
- Header: trainer label (`persona_label`), e.g. "Bartek · Motor Skills Trainer answered".
- On expand: Goat's question (smaller/grayed text, prefix "Question:") + trainer's answer (main text).
- Visually distinguished from `MessageBubble` (e.g. smaller font, border, indent) — it should read as "source preview", not another message in the conversation.

## Errors

| Case | Behavior |
|------|----------|
| `consult_persona` returns error | no `consult_detail` (live) / no entry in history (JSON parsing without `answer`) |
| Malformed JSON in `role='tool'` during history parsing | skip entry, don't break rendering of the rest of history |
| `consult_detail` arrives without a corresponding `tool_result`/Goat message (edge case on interrupted stream) | FE ignores the orphaned `consult_detail` (nothing to attach to) |

## Tests

- Backend: `_consult_persona` returns `question` in JSON (happy path).
- Backend: `consult_detail` event emitted only on `status: "ok"`, with correct `tool_call_id`.
- Backend: no `consult_detail` on error (bad slug / limit / timeout).
- FE: `chat-messages.ts` — pairing `assistant.tool_calls` (`consult_persona`) ↔ `tool` by `tool_call_id`, building `consultDetails`.
- FE: `chat-messages.ts` — malformed JSON in `role='tool'` doesn't crash history parsing.
- FE: `useChatTurnRunner` — accumulation of `consult_detail` during stream, attachment to the final message.
- FE: `ConsultDetails` — collapsed by default; expand shows question + answer; doesn't render when `consultDetails` is empty.
- FE: roundtable — 2+ consultations in one turn → 2+ elements in correct order.

## Out of scope (this iteration)

- Changing the content/format of the trainer's answer for direct user readability (today `answer` is written as "brief for Goat", not as user-facing copy — see "Open question" below).
- Ability to reply/ask the trainer directly from this panel (that would already be a step toward full multi-agent chat, out of scope for this change).
- `persona` session (1:1) and slash — unchanged, `consult_persona` doesn't occur there.
- Export/print history including consultations — not addressed.

## Open question (decide before/during implementation)

The trainer's `answer` today is generated with the idea "Goat reads this, not the user" (trainer prompt in `consult`-turn is plain `handle_message`, without knowing the text can go directly to the user's eyes). After this change the user may see raw text. To resolve:

- **Option A (recommended to start):** don't change anything in the trainer's prompt — it's still the same text, on the basis of which Goat already builds the answer today, so this isn't new "uncontrolled" content, just previously hidden. Accept that it may sound slightly "technical"/abbreviated as a source preview.
- **Option B:** add to the trainer's prompt in `consult` mode a note like "Your answer may be shown to the user as a preview — write concisely and clearly" — cost: extra branch in the prompt, risk of changing the behavior of the existing consultation path (today optimized for "brief for Goat").

Doesn't block UI implementation — can ship with option A and possibly switch to B after observing text quality in practice.

## Documents to update on implementation

- `docs/technical/team-lead.md` — new section "Consultation visibility" + update of the SSE diagram (## SSE fragment).
- `docs/technical/ai-pipeline.md` §1a — mention of `consult_detail`.
- `docs/technical/architecture.md` §3a — add `consult_detail` to the list of events in "Frontend SSE events (contract)".
- `docs/technical/frontend.md` — new `ConsultDetails` component, if the file documents chat components.
