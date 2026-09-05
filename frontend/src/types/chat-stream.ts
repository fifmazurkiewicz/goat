// SSE chat event types — DELIBERATE EXCEPTION to generation from OpenAPI (OpenAPI does not describe
// the stream), defined by hand and kept consistent with the backend contract described in
// docs/technical/architecture.md sections 3 and 3a (ADR-13: persona_turn_start).

export interface ChatStreamTokenEvent {
  type: "token";
  text: string;
}

export interface ChatStreamToolCallStartEvent {
  type: "tool_call_start";
  /** FE contract; the backend orchestrator also emits `name` — normalized in `resolveToolName`. */
  tool_name?: string;
  name?: string;
}

export interface ChatStreamToolResultEvent {
  type: "tool_result";
  tool_name: string;
  summary: string;
  success: boolean;
  /** Present for `rebuild_plan` — FE starts polling the plan job. */
  job_id?: string;
  /** Goat asked the user to confirm a full plan rebuild. */
  needs_confirm?: boolean;
}

export interface ChatStreamConsultDetailEvent {
  type: "consult_detail";
  tool_call_id: string;
  slug: string;
  persona_label: string;
  question: string;
  answer: string;
}

export interface ChatStreamDoneEvent {
  type: "done";
  message_id?: string;
}

export interface ChatStreamErrorEvent {
  type: "error";
  code?: string;
  message: string;
}

// ADR-13: emitted BEFORE the first token of the turn in a 'general' session — the frontend renders
// the header with the persona's name/avatar before the content arrives.
export interface ChatStreamPersonaTurnStartEvent {
  type: "persona_turn_start";
  /** `null` for Goat (Team Lead) — ADR-17 */
  persona_id: string | null;
  persona_label: string;
}

export interface ChatStreamTeamStatusEvent {
  type: "team_status";
  message: string;
}

export type PersonaStatusPhase = "thinking" | "writing" | "tool" | "wrapping_up" | "done";

export interface ChatStreamPersonaStatusEvent {
  type: "persona_status";
  persona_id: string | null;
  persona_label: string;
  phase: PersonaStatusPhase;
  message: string;
  tool_name?: string;
}

export interface ChatStreamTeamPhaseEvent {
  type: "team_phase";
  phase: "planning" | "delegating" | "synthesizing";
  message: string;
}

export interface ChatStreamPersonaTurnEndEvent {
  type: "persona_turn_end";
  persona_id: string | null;
  persona_label: string;
}

export interface ChatStreamTurnCompleteEvent {
  type: "turn_complete";
  persona_count?: number;
}

export type ChatStreamEvent =
  | ChatStreamTokenEvent
  | ChatStreamToolCallStartEvent
  | ChatStreamToolResultEvent
  | ChatStreamConsultDetailEvent
  | ChatStreamPersonaTurnStartEvent
  | ChatStreamPersonaStatusEvent
  | ChatStreamTeamPhaseEvent
  | ChatStreamPersonaTurnEndEvent
  | ChatStreamTeamStatusEvent
  | ChatStreamTurnCompleteEvent
  | ChatStreamDoneEvent
  | ChatStreamErrorEvent;

export interface SendMessageBody {
  content: string;
  /** Retry after a stream error — the backend does not insert the same user message twice. */
  retry?: boolean;
}
