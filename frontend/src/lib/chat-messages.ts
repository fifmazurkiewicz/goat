import type { ChatMessage, ConsultDetail } from "@/types/api";

/**
 * Wiadomości widoczne w UI — bez `role=tool` (surowe JSON-y narzędzi)
 * i bez pustych `assistant` (tury tylko z tool_calls).
 * Historia tooli zostaje w DB dla LLM; user widzi najwyżej ToolResultChip ze streamu.
 *
 * Od 2026-08-22 (widoczność konsultacji): `role='tool'` będący udaną odpowiedzią
 * `consult_persona` jest parowany z wywołaniem w `tool_calls` poprzedzającej wiadomości
 * Goata (po `tool_call_id`, które backend trzyma w `tool_calls.tool_call_id`) i doczepiany
 * jako `consultDetails` — podgląd „co trener powiedział Goatowi" bez osobnej wiadomości
 * trenera (ADR-17 nietknięty). Stare wpisy bez `question` dostają puste pytanie; złamany
 * JSON pomijany.
 */
export function visibleChatMessages(messages: ChatMessage[]): ChatMessage[] {
  const seen = new Set<string>();
  const out: ChatMessage[] = [];
  // tool_call_id → indeks wiadomości Goata w `out` + argumenty wywołania (fallback `question`
  // dla starych wpisów historii sprzed 2026-08-22, gdy tool response nie miał pola).
  const consultTargets = new Map<string, { index: number; args: Record<string, unknown> }>();
  for (const message of messages) {
    const hasConsults = message.role === "assistant" && consultCallMap(message).size > 0;
    if (
      message.role === "assistant" &&
      !(message.content ?? "").trim() &&
      !hasConsults
    ) {
      continue;
    }
    if (message.role === "tool") {
      appendConsultDetail(message, out, consultTargets);
      continue;
    }
    if (seen.has(message.id)) continue;
    seen.add(message.id);
    if (message.role === "assistant") {
      registerConsultTargets(message, out, consultTargets);
    }
    out.push(message);
  }
  return out;
}

/** tool_call_id → argumenty wywołań `consult_persona` z `assistant.tool_calls`. */
function consultCallMap(message: ChatMessage): Map<string, Record<string, unknown>> {
  const map = new Map<string, Record<string, unknown>>();
  const calls = (message.tool_calls as { calls?: unknown } | null)?.calls;
  if (!Array.isArray(calls)) return map;
  for (const call of calls as Array<Record<string, unknown>>) {
    const fn = call?.function as { name?: unknown; arguments?: unknown } | undefined;
    if (fn?.name !== "consult_persona" || typeof call?.id !== "string") continue;
    let args: Record<string, unknown> = {};
    if (typeof fn.arguments === "string") {
      try {
        args = JSON.parse(fn.arguments) as Record<string, unknown>;
      } catch {
        args = {};
      }
    }
    map.set(call.id, args);
  }
  return map;
}

/** Rejestruje wiadomość Goata jako cel konsultacji dla każdego jej `consult_persona`. */
function registerConsultTargets(
  message: ChatMessage,
  out: ChatMessage[],
  targets: Map<string, { index: number; args: Record<string, unknown> }>
): void {
  const index = out.length;
  for (const [id, args] of consultCallMap(message)) {
    targets.set(id, { index, args });
  }
}

/** Doczepia konsultację do wiadomości Goata po `tool_call_id`; dedup po id (retry). */
function appendConsultDetail(
  message: ChatMessage,
  out: ChatMessage[],
  targets: Map<string, { index: number; args: Record<string, unknown> }>
): void {
  const toolCallId = (message.tool_calls as { tool_call_id?: unknown } | null)?.tool_call_id;
  if (typeof toolCallId !== "string") return;
  const target = targets.get(toolCallId);
  if (!target || !out[target.index]) return;
  const detail = parseConsultToolMessage(message, target.args);
  if (!detail) return;
  const host = out[target.index];
  if ((host.consultDetails ?? []).some((d) => d.toolCallId === toolCallId)) return;
  host.consultDetails = [...(host.consultDetails ?? []), detail];
}

/** Parsuje `role='tool'` jako konsultację; null gdy to inne narzędzie / błąd / złamany JSON. */
function parseConsultToolMessage(
  message: ChatMessage,
  callArgs: Record<string, unknown>
): ConsultDetail | null {
  if (!message.content) return null;
  try {
    const parsed = JSON.parse(message.content) as Record<string, unknown>;
    if (parsed?.status !== "ok" || typeof parsed.answer !== "string" || !parsed.answer.trim()) {
      return null;
    }
    // Stare wpisy (sprzed zmiany) nie mają `question` — fallback z argumentów tool call.
    const question =
      typeof parsed.question === "string" && parsed.question.trim()
        ? parsed.question
        : typeof callArgs.question === "string"
          ? callArgs.question
          : "";
    const personaLabel =
      typeof parsed.persona_label === "string" && parsed.persona_label.trim()
        ? parsed.persona_label
        : typeof callArgs.slug === "string"
          ? callArgs.slug
          : "Trener";
    return {
      toolCallId:
        typeof (message.tool_calls as { tool_call_id?: unknown } | null)?.tool_call_id === "string"
          ? (message.tool_calls as { tool_call_id: string }).tool_call_id
          : "",
      personaLabel,
      question,
      answer: parsed.answer,
    };
  } catch {
    return null;
  }
}

/** Czytelny komunikat z eventu SSE `error` (bez surowego JSON / escape'ów `\uXXXX`). */
export function streamErrorMessage(event: { message?: unknown; code?: unknown }): string {
  const raw = event.message;
  if (typeof raw === "string" && raw.trim()) {
    const trimmed = raw.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      const extracted = extractJsonMessage(trimmed);
      if (extracted) return extracted;
    }
    return trimmed.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex: string) =>
      String.fromCharCode(Number.parseInt(hex, 16))
    );
  }
  if (typeof event.code === "string" && event.code) {
    return `Błąd czatu (${event.code}).`;
  }
  return "Wystąpił nieoczekiwany błąd czatu.";
}

function extractJsonMessage(text: string): string | null {
  // SSE czasem skleja dwa eventy w jeden chunk — bierzemy ostatni obiekt z polem message.
  const objects = text.match(/\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}/g) ?? [text];
  for (let i = objects.length - 1; i >= 0; i -= 1) {
    try {
      const parsed = JSON.parse(objects[i]) as { message?: unknown };
      if (typeof parsed.message === "string" && parsed.message.trim()) {
        return parsed.message.trim();
      }
    } catch {
      // kolejny kandydat
    }
  }
  return null;
}
