import type { QueryClient } from "@tanstack/react-query";

import { messagesKey } from "@/hooks/useChatSessions";
import type { ChatMessage, ConsultDetail } from "@/types/api";
import type { ChatStreamToolResultEvent } from "@/types/chat-stream";

/** Attaches a finished persona turn to the cache before the next one starts (multi-reply). */
export function finalizeStreamingTurn(
  queryClient: QueryClient,
  sessionId: string,
  turn: {
    content: string;
    personaId: string | null;
    toolResults: ChatStreamToolResultEvent[];
    consultDetails?: ConsultDetail[];
  }
): void {
  if (!turn.content.trim() && turn.toolResults.length === 0 && !(turn.consultDetails ?? []).length) {
    return;
  }
  const id = `streamed-${turn.personaId ?? "x"}-${Date.now()}`;
  queryClient.setQueryData<ChatMessage[]>(messagesKey(sessionId), (old) => [
    ...(old ?? []),
    {
      id,
      session_id: sessionId,
      role: "assistant",
      content: turn.content,
      tool_calls: null,
      persona_id: turn.personaId,
      invoked_via: null,
      created_at: new Date().toISOString(),
      // Dedup by toolCallId: a background invalidate may already bring consult details
      // from history parsing — don't duplicate the entry from live.
      consultDetails: dedupeConsultDetails(turn.consultDetails ?? [], old ?? []),
    },
  ]);
}

function dedupeConsultDetails(live: ConsultDetail[], existing: ChatMessage[] | undefined): ConsultDetail[] | undefined {
  if (live.length === 0) return undefined;
  const known = new Set<string>();
  for (const message of existing ?? []) {
    for (const detail of message.consultDetails ?? []) {
      if (detail.toolCallId) known.add(detail.toolCallId);
    }
  }
  const filtered = live.filter((detail) => !known.has(detail.toolCallId));
  return filtered.length > 0 ? filtered : undefined;
}
