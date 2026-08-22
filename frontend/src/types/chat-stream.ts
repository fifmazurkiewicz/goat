// Typy eventów SSE czatu — ŚWIADOMY WYJĄTEK od generacji z OpenAPI (OpenAPI nie opisuje
// strumienia), definiowane ręcznie i utrzymywane w zgodzie z kontraktem backendu opisanym
// w docs/technical/architecture.md sekcja 3 i 3a (ADR-13: persona_turn_start).

export interface ChatStreamTokenEvent {
  type: "token";
  text: string;
}

export interface ChatStreamToolCallStartEvent {
  type: "tool_call_start";
  /** Kontrakt FE; backend orkiestratora emituje też `name` — normalizacja w `resolveToolName`. */
  tool_name?: string;
  name?: string;
}

export interface ChatStreamToolResultEvent {
  type: "tool_result";
  tool_name: string;
  summary: string;
  success: boolean;
  /** Obecne przy `rebuild_plan` — FE startuje polling joba planu. */
  job_id?: string;
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

// ADR-13: emitowany PRZED pierwszym tokenem tury w sesji 'general' — frontend renderuje
// nagłówek z nazwą/awatarem persony zanim przyjdzie treść.
export interface ChatStreamPersonaTurnStartEvent {
  type: "persona_turn_start";
  /** `null` dla Goata (Kierownik Zespołu) — ADR-17 */
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
  /** Ponowienie po błędzie streamu — backend nie wstawia drugi raz tej samej wiadomości usera. */
  retry?: boolean;
}
