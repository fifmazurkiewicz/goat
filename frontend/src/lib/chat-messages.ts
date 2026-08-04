import type { ChatMessage } from "@/types/api";

/**
 * Wiadomości widoczne w UI — bez `role=tool` (surowe JSON-y narzędzi)
 * i bez pustych `assistant` (tury tylko z tool_calls).
 * Historia tooli zostaje w DB dla LLM; user widzi najwyżej ToolResultChip ze streamu.
 */
export function visibleChatMessages(messages: ChatMessage[]): ChatMessage[] {
  const seen = new Set<string>();
  const out: ChatMessage[] = [];
  for (const message of messages) {
    if (message.role === "tool") continue;
    if (message.role === "assistant" && !(message.content ?? "").trim()) continue;
    if (seen.has(message.id)) continue;
    seen.add(message.id);
    out.push(message);
  }
  return out;
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
