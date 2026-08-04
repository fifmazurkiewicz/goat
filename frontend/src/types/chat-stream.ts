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
  persona_id: string;
  persona_label: string;
}

export type ChatStreamEvent =
  | ChatStreamTokenEvent
  | ChatStreamToolCallStartEvent
  | ChatStreamToolResultEvent
  | ChatStreamPersonaTurnStartEvent
  | ChatStreamDoneEvent
  | ChatStreamErrorEvent;

export interface SendMessageBody {
  content: string;
  /** Ponowienie po błędzie streamu — backend nie wstawia drugi raz tej samej wiadomości usera. */
  retry?: boolean;
}
