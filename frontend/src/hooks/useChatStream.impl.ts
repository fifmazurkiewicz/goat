import type { QueryClient } from "@tanstack/react-query";

import { messagesKey } from "@/hooks/useChatSessions";
import type { ChatMessage } from "@/types/api";
import type { ChatStreamToolResultEvent } from "@/types/chat-stream";

/** Dopina ukończoną turę persony do cache zanim wystartuje kolejna (multi-reply). */
export function finalizeStreamingTurn(
  queryClient: QueryClient,
  sessionId: string,
  turn: {
    content: string;
    personaId: string | null;
    toolResults: ChatStreamToolResultEvent[];
  }
): void {
  if (!turn.content.trim() && turn.toolResults.length === 0) return;
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
    },
  ]);
}
