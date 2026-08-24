import { useCallback } from "react";

import { useChatTurnStore } from "@/store/useChatTurnStore";

export type { ChatStreamError, StreamingAssistantMessage } from "@/store/useChatTurnStore";

export interface UseChatStreamOptions {
  sessionType?: string;
}

/**
 * Thin layer over the global `useChatTurnStore` + `useChatTurnRunner` in AppShell.
 * Stream survives navigation to Results/Plans.
 */
export function useChatStream(sessionId: string | undefined, options?: UseChatStreamOptions) {
  const sessionType = options?.sessionType ?? "persona";
  const queueTurn = useChatTurnStore((s) => s.queueTurn);
  const stopTurn = useChatTurnStore((s) => s.stopTurn);
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

  const stopGeneration = useCallback(() => {
    if (!sessionId || !isStreaming) return;
    stopTurn(sessionId);
  }, [sessionId, isStreaming, stopTurn]);

  return { sendMessage, retry, stopGeneration, clearError, isStreaming, streaming, error };
}

/** Re-export for useChatTurnRunner — attaches the finished turn to the history cache. */
export { finalizeStreamingTurn } from "@/hooks/useChatStream.impl";
