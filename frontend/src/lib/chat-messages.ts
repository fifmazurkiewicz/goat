import type { ChatMessage, ConsultDetail } from "@/types/api";

/**
 * Messages visible in the UI — without `role=tool` (raw tool JSONs)
 * and without empty `assistant` (turns with only tool_calls).
 * Tool history stays in the DB for the LLM; the user sees at most a ToolResultChip from the stream.
 *
 * Since 2026-08-22 (consult visibility): a `role='tool'` entry that is a successful response
 * to `consult_persona` is paired with the call in `tool_calls` of the preceding Goat message
 * (by `tool_call_id`, which the backend keeps in `tool_calls.tool_call_id`) and attached
 * as `consultDetails` — a peek at "what the trainer told Goat" without a separate trainer
 * message (ADR-17 untouched). Old entries without `question` get an empty question; broken
 * JSON is skipped.
 */
export function visibleChatMessages(messages: ChatMessage[]): ChatMessage[] {
  const seen = new Set<string>();
  const out: ChatMessage[] = [];
  // tool_call_id → index of the Goat message in `out` + call arguments (fallback `question`
  // for old history entries before 2026-08-22, when the tool response didn't have the field).
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

/** tool_call_id → arguments of `consult_persona` calls from `assistant.tool_calls`. */
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

/** Registers a Goat message as a consult target for each of its `consult_persona` calls. */
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

/** Attaches a consult to a Goat message by `tool_call_id`; dedup by id (retry). */
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

/** Parses `role='tool'` as a consult; null when it's another tool / error / broken JSON. */
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
    // Old entries (before the change) don't have `question` — fallback from tool call arguments.
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

/** Readable message from an SSE `error` event (without raw JSON / `\uXXXX` escapes). */
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
  // SSE sometimes glues two events into one chunk — we take the last object with a message field.
  const objects = text.match(/\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}/g) ?? [text];
  for (let i = objects.length - 1; i >= 0; i -= 1) {
    try {
      const parsed = JSON.parse(objects[i]) as { message?: unknown };
      if (typeof parsed.message === "string" && parsed.message.trim()) {
        return parsed.message.trim();
      }
    } catch {
      // next candidate
    }
  }
  return null;
}
