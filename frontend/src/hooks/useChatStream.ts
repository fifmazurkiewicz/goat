import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api-client";
import { streamChatMessage } from "@/lib/sse";
import { messagesKey } from "@/hooks/useChatSessions";
import { useRefreshUsage } from "@/hooks/useUsage";
import type { ChatMessage } from "@/types/api";
import type { ChatStreamToolResultEvent } from "@/types/chat-stream";

export interface StreamingAssistantMessage {
  content: string;
  personaId: string | null;
  personaLabel: string | null;
  toolResults: ChatStreamToolResultEvent[];
}

export interface ChatStreamError {
  message: string;
  canRetry: boolean;
}

const emptyStreaming = (): StreamingAssistantMessage => ({
  content: "",
  personaId: null,
  personaLabel: null,
  toolResults: [],
});

/**
 * JEDYNE miejsce otwierające/zamykające SSE (docs/technical/frontend.md sekcja 4).
 * `fetch` + `ReadableStream` (nie `EventSource`, sekcja 3) przez `streamChatMessage`.
 * Batchuje tokeny przez `requestAnimationFrame` zamiast re-renderować przy każdym
 * fragmencie, i invaliduje `['results']` po `tool_result` (sekcja 2).
 */
export function useChatStream(sessionId: string | undefined) {
  const queryClient = useQueryClient();
  const refreshUsage = useRefreshUsage();

  const [isStreaming, setIsStreaming] = useState(false);
  const [streaming, setStreaming] = useState<StreamingAssistantMessage | null>(null);
  const [error, setError] = useState<ChatStreamError | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const pendingContentRef = useRef("");
  const rafRef = useRef<number | null>(null);
  const lastContentRef = useRef<string>("");

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [sessionId]);

  const flushTokens = useCallback(() => {
    rafRef.current = null;
    setStreaming((prev) => (prev ? { ...prev, content: pendingContentRef.current } : prev));
  }, []);

  const scheduleFlush = useCallback(() => {
    if (rafRef.current == null) {
      rafRef.current = requestAnimationFrame(flushTokens);
    }
  }, [flushTokens]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!sessionId || isStreaming) return;

      lastContentRef.current = content;
      setError(null);
      setIsStreaming(true);
      pendingContentRef.current = "";
      setStreaming(emptyStreaming());

      const controller = new AbortController();
      abortControllerRef.current = controller;

      queryClient.setQueryData<ChatMessage[]>(messagesKey(sessionId), (old) => [
        ...(old ?? []),
        {
          id: `optimistic-${Date.now()}`,
          session_id: sessionId,
          role: "user",
          content,
          tool_calls: null,
          persona_id: null,
          invoked_via: null,
          created_at: new Date().toISOString(),
        },
      ]);

      try {
        for await (const event of streamChatMessage({ sessionId, body: { content }, signal: controller.signal })) {
          switch (event.type) {
            case "persona_turn_start":
              setStreaming((prev) => ({
                ...(prev ?? emptyStreaming()),
                personaId: event.persona_id,
                personaLabel: event.persona_label,
              }));
              break;
            case "token":
              pendingContentRef.current += event.text;
              scheduleFlush();
              break;
            case "tool_call_start":
              break;
            case "tool_result":
              setStreaming((prev) => ({
                ...(prev ?? emptyStreaming()),
                toolResults: [...(prev?.toolResults ?? []), event],
              }));
              void queryClient.invalidateQueries({ queryKey: ["results"] });
              refreshUsage();
              break;
            case "error":
              setError({ message: event.message, canRetry: true });
              break;
            case "done":
              break;
          }
        }
      } catch (err) {
        if (controller.signal.aborted) {
          // Nawigacja/odmontowanie przerwało stream — nie traktuj jako błąd usera.
        } else if (err instanceof ApiError && err.status === 401) {
          setError({ message: "Sesja wygasła, zaloguj się ponownie.", canRetry: false });
        } else if (err instanceof ApiError && err.status === 429) {
          setError({ message: err.message, canRetry: false });
          refreshUsage();
        } else {
          setError({ message: "Połączenie przerwane.", canRetry: true });
        }
      } finally {
        setIsStreaming(false);
        setStreaming(null);
        if (sessionId) {
          void queryClient.invalidateQueries({ queryKey: messagesKey(sessionId) });
        }
      }
    },
    [sessionId, isStreaming, queryClient, scheduleFlush, refreshUsage]
  );

  const retry = useCallback(() => {
    if (lastContentRef.current) void sendMessage(lastContentRef.current);
  }, [sendMessage]);

  const clearError = useCallback(() => setError(null), []);

  return { sendMessage, retry, clearError, isStreaming, streaming, error };
}
