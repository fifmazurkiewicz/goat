import { useCallback } from "react";

import { useChatTurnStore } from "@/store/useChatTurnStore";

export type { ChatStreamError, StreamingAssistantMessage } from "@/store/useChatTurnStore";

export interface UseChatStreamOptions {
  sessionType?: string;
}

/**
 * Cienka warstwa nad globalnym `useChatTurnStore` + `useChatTurnRunner` w AppShell.
 * Stream nie ginie przy nawigacji do Wyniki/Plany.
 */
export function useChatStream(sessionId: string | undefined, options?: UseChatStreamOptions) {
  const sessionType = options?.sessionType ?? "persona";
  const queueTurn = useChatTurnStore((s) => s.queueTurn);
  const lastContent = useChatTurnStore((s) => s.lastContent);
  const clearError = useCallback(() => {
    useChatTurnStore.setState({ error: null });
  }, []);

  const isStreaming = useChatTurnStore(
    (s) => Boolean(sessionId && s.isStreaming && s.sessionId === sessionId)
  );
  const streaming = useChatTurnStore((s) =>
    sessionId && s.sessionId === sessionId ? s.streaming : null
  );
  const error = useChatTurnStore((s) => (sessionId && s.sessionId === sessionId ? s.error : null));

  const sendMessage = useCallback(
    (content: string, opts?: { retry?: boolean }) => {
      if (!sessionId || isStreaming) return;
      queueTurn({
        sessionId,
        content,
        sessionType,
        retry: Boolean(opts?.retry),
      });
    },
    [sessionId, sessionType, isStreaming, queueTurn]
  );

  const retry = useCallback(() => {
    if (lastContent) void sendMessage(lastContent, { retry: true });
  }, [lastContent, sendMessage]);

  return { sendMessage, retry, clearError, isStreaming, streaming, error };
}

/** Re-eksport dla useChatTurnRunner — dopina ukończoną turę do cache historii. */
export { finalizeStreamingTurn } from "@/hooks/useChatStream.impl";
