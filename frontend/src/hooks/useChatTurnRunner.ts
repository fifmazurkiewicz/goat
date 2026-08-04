import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError } from "@/lib/api-client";
import { streamErrorMessage } from "@/lib/chat-messages";
import {
  initialStreamStatus,
  personaThinkingStatus,
  personaToolStatus,
  resolveToolName,
  teamStatusLabel,
  TEAM_STATUS_DEFAULT,
} from "@/lib/chat-status";
import { streamChatMessage } from "@/lib/sse";
import {
  registerChatTurnAbort,
  unregisterChatTurnAbort,
} from "@/lib/chat-turn-control";
import { messagesKey } from "@/hooks/useChatSessions";
import { finalizeStreamingTurn } from "@/hooks/useChatStream.impl";
import { useRefreshUsage } from "@/hooks/useUsage";
import { useChatTurnStore, type StreamingAssistantMessage } from "@/store/useChatTurnStore";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";
import type { ChatMessage } from "@/types/api";
import type { ChatStreamToolResultEvent } from "@/types/chat-stream";

const PLAN_TOOL_NAMES = new Set(["get_plan", "upsert_plan_items", "rebuild_plan"]);

const emptyStreaming = (statusLabel: string | null = null): StreamingAssistantMessage => ({
  content: "",
  personaId: null,
  personaLabel: null,
  statusLabel,
  toolResults: [],
});

/**
 * Globalny runner tur czatu — mount w AppShell (jak polling planów).
 * Kontynuuje stream po nawigacji poza /chat.
 */
export function useChatTurnRunner() {
  const queryClient = useQueryClient();
  const refreshUsage = useRefreshUsage();
  const pending = useChatTurnStore((s) => s.pending);
  const clearPending = useChatTurnStore((s) => s.clearPending);
  const setStreamingState = useChatTurnStore((s) => s.setStreamingState);
  const setLastContent = useChatTurnStore((s) => s.setLastContent);
  const removeBackgroundSession = useChatTurnStore((s) => s.removeBackgroundSession);

  const runningRef = useRef(false);

  useEffect(() => {
    if (!pending || runningRef.current) return;

    const { sessionId, content, sessionType, retry } = pending;
    clearPending();
    runningRef.current = true;

    const controller = new AbortController();
    registerChatTurnAbort(sessionId, controller);

    setLastContent(content);
    setStreamingState({
      isStreaming: true,
      streaming: emptyStreaming(initialStreamStatus(sessionType)),
      error: null,
    });

    const isRetry = Boolean(retry);
    if (!isRetry) {
      queryClient.setQueryData<ChatMessage[]>(messagesKey(sessionId), (old) => [
        ...(old ?? []).filter((m) => !m.id.startsWith("optimistic-")),
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
    }

    let pendingContent = "";
    let personaLabel: string | null = null;
    let personaId: string | null = null;
    let toolResults: ChatStreamToolResultEvent[] = [];
    let turnActive = false;
    let planToolsTouched = false;
    let raf: number | null = null;

    const flushTokens = () => {
      raf = null;
      setStreamingState({
        streaming: {
          content: pendingContent,
          personaId,
          personaLabel,
          statusLabel: null,
          toolResults: [...toolResults],
        },
      });
    };

    const scheduleFlush = () => {
      if (raf == null) raf = requestAnimationFrame(flushTokens);
    };

    const syncFlush = () => {
      if (raf != null) {
        cancelAnimationFrame(raf);
        raf = null;
      }
    };

    void (async () => {
      try {
        for await (const event of streamChatMessage({
          sessionId,
          body: { content, retry: isRetry || undefined },
          signal: controller.signal,
        })) {
          switch (event.type) {
            case "team_status":
              setStreamingState({
                streaming: {
                  ...emptyStreaming(),
                  statusLabel: teamStatusLabel(
                    typeof event.message === "string" ? event.message : null
                  ),
                },
              });
              break;
            case "team_phase":
              setStreamingState({
                streaming: {
                  ...emptyStreaming(),
                  statusLabel:
                    typeof event.message === "string" ? event.message : TEAM_STATUS_DEFAULT,
                },
              });
              break;
            case "persona_status":
              setStreamingState({
                streaming: {
                  content: pendingContent,
                  personaId: event.persona_id,
                  personaLabel: event.persona_label,
                  statusLabel: event.message,
                  toolResults: [...toolResults],
                },
              });
              break;
            case "persona_turn_end":
              setStreamingState({
                streaming: {
                  content: pendingContent,
                  personaId: event.persona_id,
                  personaLabel: event.persona_label,
                  statusLabel: `${event.persona_label} zakończył(a) odpowiedź`,
                  toolResults: [...toolResults],
                },
              });
              break;
            case "persona_turn_start":
              if (turnActive) {
                syncFlush();
                finalizeStreamingTurn(queryClient, sessionId, {
                  content: pendingContent,
                  personaId,
                  toolResults,
                });
              }
              turnActive = true;
              pendingContent = "";
              toolResults = [];
              personaId = event.persona_id;
              personaLabel = event.persona_label;
              setStreamingState({
                streaming: {
                  content: "",
                  personaId: event.persona_id,
                  personaLabel: event.persona_label,
                  statusLabel: personaThinkingStatus(event.persona_label),
                  toolResults: [],
                },
              });
              break;
            case "token":
              pendingContent += event.text;
              scheduleFlush();
              break;
            case "tool_call_start": {
              const toolName = resolveToolName(event);
              if (!toolName) break;
              if (PLAN_TOOL_NAMES.has(toolName)) planToolsTouched = true;
              setStreamingState({
                streaming: {
                  content: pendingContent,
                  personaId,
                  personaLabel,
                  statusLabel: personaToolStatus(personaLabel, toolName),
                  toolResults: [...toolResults],
                },
              });
              break;
            }
            case "tool_result": {
              toolResults = [...toolResults, event];
              if (PLAN_TOOL_NAMES.has(event.tool_name)) planToolsTouched = true;
              if (event.tool_name === "upsert_plan_items" && event.success) {
                toast.success(event.summary || "Zapisano pozycje w Plany");
              }
              setStreamingState({
                streaming: {
                  content: pendingContent,
                  personaId,
                  personaLabel,
                  statusLabel: personaThinkingStatus(personaLabel),
                  toolResults,
                },
              });
              void queryClient.invalidateQueries({ queryKey: ["results"] });
              if (PLAN_TOOL_NAMES.has(event.tool_name)) {
                void queryClient.invalidateQueries({ queryKey: ["plans"] });
              }
              if (event.tool_name === "rebuild_plan" && event.job_id) {
                usePlanGenerationStore.getState().startJob(event.job_id);
              }
              refreshUsage();
              break;
            }
            case "turn_complete":
              setStreamingState({
                streaming: {
                  content: pendingContent,
                  personaId,
                  personaLabel,
                  statusLabel: "Zespół zakończył odpowiedź",
                  toolResults: [...toolResults],
                },
              });
              break;
            case "error":
              setStreamingState({
                error: { message: streamErrorMessage(event), canRetry: true },
              });
              break;
            case "done":
              break;
          }
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          if (err instanceof ApiError && err.status === 401) {
            setStreamingState({
              error: { message: "Sesja wygasła, zaloguj się ponownie.", canRetry: false },
            });
          } else if (err instanceof ApiError && err.status === 429) {
            setStreamingState({ error: { message: err.message, canRetry: false } });
            refreshUsage();
          } else {
            setStreamingState({ error: { message: "Połączenie przerwane.", canRetry: true } });
          }
        }
      } finally {
        syncFlush();
        const userStopped = controller.signal.aborted;
        if (turnActive && (pendingContent.trim() || toolResults.length > 0)) {
          finalizeStreamingTurn(queryClient, sessionId, {
            content: pendingContent,
            personaId,
            toolResults,
          });
        }
        setStreamingState({ isStreaming: false, streaming: null });
        removeBackgroundSession(sessionId);
        if (!userStopped) {
          void queryClient.invalidateQueries({ queryKey: messagesKey(sessionId) });
        }
        void queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
        if (planToolsTouched) {
          void queryClient.invalidateQueries({ queryKey: ["plans"] });
        }
        runningRef.current = false;
        unregisterChatTurnAbort(sessionId);
      }
    })();
  }, [
    pending,
    clearPending,
    queryClient,
    refreshUsage,
    setStreamingState,
    setLastContent,
    removeBackgroundSession,
  ]);
}
