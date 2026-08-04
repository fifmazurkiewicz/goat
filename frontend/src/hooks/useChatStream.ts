import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api-client";
import { streamErrorMessage } from "@/lib/chat-messages";
import {
  initialStreamStatus,
  personaThinkingStatus,
  personaToolStatus,
  resolveToolName,
} from "@/lib/chat-status";
import { streamChatMessage } from "@/lib/sse";
import { messagesKey } from "@/hooks/useChatSessions";
import { useRefreshUsage } from "@/hooks/useUsage";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";
import type { ChatMessage } from "@/types/api";
import type { ChatStreamToolResultEvent } from "@/types/chat-stream";

export interface StreamingAssistantMessage {
  content: string;
  personaId: string | null;
  personaLabel: string | null;
  /** Jedna linia statusu — null gdy lecą tokeny lub stream nieaktywny. */
  statusLabel: string | null;
  toolResults: ChatStreamToolResultEvent[];
}

export interface ChatStreamError {
  message: string;
  canRetry: boolean;
}

const emptyStreaming = (statusLabel: string | null = null): StreamingAssistantMessage => ({
  content: "",
  personaId: null,
  personaLabel: null,
  statusLabel,
  toolResults: [],
});

export interface UseChatStreamOptions {
  /** `general` → start od „Dobieram trenera…”; `persona` → „Przygotowuję odpowiedź…”. */
  sessionType?: string;
}

const PLAN_TOOL_NAMES = new Set(["get_plan", "upsert_plan_items", "rebuild_plan"]);

/**
 * JEDYNE miejsce otwierające/zamykające SSE (docs/technical/frontend.md sekcja 4).
 * Multi-persona: kolejne `persona_turn_start` finalizują poprzednią odpowiedź do cache historii.
 */
export function useChatStream(sessionId: string | undefined, options?: UseChatStreamOptions) {
  const queryClient = useQueryClient();
  const refreshUsage = useRefreshUsage();
  const sessionType = options?.sessionType ?? "persona";

  const [isStreaming, setIsStreaming] = useState(false);
  const [streaming, setStreaming] = useState<StreamingAssistantMessage | null>(null);
  const [error, setError] = useState<ChatStreamError | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const pendingContentRef = useRef("");
  const rafRef = useRef<number | null>(null);
  const lastContentRef = useRef<string>("");
  const personaLabelRef = useRef<string | null>(null);
  const personaIdRef = useRef<string | null>(null);
  const toolResultsRef = useRef<ChatStreamToolResultEvent[]>([]);
  const turnActiveRef = useRef(false);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [sessionId]);

  const flushTokens = useCallback(() => {
    rafRef.current = null;
    setStreaming((prev) =>
      prev ? { ...prev, content: pendingContentRef.current, statusLabel: null } : prev
    );
  }, []);

  const scheduleFlush = useCallback(() => {
    if (rafRef.current == null) {
      rafRef.current = requestAnimationFrame(flushTokens);
    }
  }, [flushTokens]);

  const sendMessage = useCallback(
    async (content: string, options?: { retry?: boolean }) => {
      if (!sessionId || isStreaming) return;

      lastContentRef.current = content;
      personaLabelRef.current = null;
      personaIdRef.current = null;
      toolResultsRef.current = [];
      turnActiveRef.current = false;
      setError(null);
      setIsStreaming(true);
      pendingContentRef.current = "";
      setStreaming(emptyStreaming(initialStreamStatus(sessionType)));

      const controller = new AbortController();
      abortControllerRef.current = controller;

      const isRetry = Boolean(options?.retry);
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

      const syncFlushPending = () => {
        if (rafRef.current != null) {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        }
      };

      try {
        for await (const event of streamChatMessage({
          sessionId,
          body: { content, retry: isRetry || undefined },
          signal: controller.signal,
        })) {
          switch (event.type) {
            case "persona_turn_start":
              if (turnActiveRef.current) {
                syncFlushPending();
                finalizeStreamingTurn(queryClient, sessionId, {
                  content: pendingContentRef.current,
                  personaId: personaIdRef.current,
                  toolResults: toolResultsRef.current,
                });
              }
              turnActiveRef.current = true;
              pendingContentRef.current = "";
              toolResultsRef.current = [];
              personaIdRef.current = event.persona_id;
              personaLabelRef.current = event.persona_label;
              setStreaming({
                content: "",
                personaId: event.persona_id,
                personaLabel: event.persona_label,
                statusLabel: personaThinkingStatus(event.persona_label),
                toolResults: [],
              });
              break;
            case "token":
              pendingContentRef.current += event.text;
              scheduleFlush();
              break;
            case "tool_call_start": {
              const toolName = resolveToolName(event);
              if (!toolName) break;
              setStreaming((prev) => ({
                ...(prev ?? emptyStreaming()),
                statusLabel: personaToolStatus(personaLabelRef.current ?? prev?.personaLabel, toolName),
              }));
              break;
            }
            case "tool_result": {
              const normalized = normalizeToolResultEvent(
                event as ChatStreamToolResultEvent & Record<string, unknown>
              );
              toolResultsRef.current = [...toolResultsRef.current, normalized];
              setStreaming((prev) => ({
                ...(prev ?? emptyStreaming()),
                statusLabel: personaThinkingStatus(personaLabelRef.current ?? prev?.personaLabel),
                toolResults: toolResultsRef.current,
              }));
              void queryClient.invalidateQueries({ queryKey: ["results"] });
              if (PLAN_TOOL_NAMES.has(normalized.tool_name)) {
                void queryClient.invalidateQueries({ queryKey: ["plans"] });
              }
              const jobId =
                typeof (event as { job_id?: unknown }).job_id === "string"
                  ? (event as { job_id: string }).job_id
                  : null;
              if (normalized.tool_name === "rebuild_plan" && jobId) {
                usePlanGenerationStore.getState().startJob(jobId);
              }
              refreshUsage();
              break;
            }
            case "error":
              setError({ message: streamErrorMessage(event), canRetry: true });
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
    [sessionId, sessionType, isStreaming, queryClient, scheduleFlush, refreshUsage]
  );

  const retry = useCallback(() => {
    if (lastContentRef.current) void sendMessage(lastContentRef.current, { retry: true });
  }, [sendMessage]);

  const clearError = useCallback(() => setError(null), []);

  return { sendMessage, retry, clearError, isStreaming, streaming, error };
}

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

/** Backend bywa z `{name, result}` — FE kontrakt to `{tool_name, summary, success}`. */
function normalizeToolResultEvent(
  event: ChatStreamToolResultEvent & Record<string, unknown>
): ChatStreamToolResultEvent {
  if (typeof event.tool_name === "string" && typeof event.summary === "string") {
    return {
      type: "tool_result",
      tool_name: event.tool_name,
      summary: event.summary,
      success: Boolean(event.success),
      ...(typeof event.job_id === "string" ? { job_id: event.job_id } : {}),
    };
  }

  const name =
    (typeof event.tool_name === "string" && event.tool_name) ||
    (typeof event.name === "string" && event.name) ||
    "narzędzie";
  const rawResult = typeof event.result === "string" ? event.result : event.summary;
  const { summary, success } = summarizeToolResult(name, rawResult);
  return { type: "tool_result", tool_name: name, summary, success };
}

function summarizeToolResult(toolName: string, raw: unknown): { summary: string; success: boolean } {
  if (typeof raw !== "string" || !raw.trim()) {
    return { summary: toolName === "log_result" ? "Zapisano wynik" : "Zaktualizowano dane", success: true };
  }
  try {
    const parsed = JSON.parse(raw) as {
      error?: string;
      status?: string;
      updated_fields?: string[];
      results?: Array<{ status?: string; error?: string | null }>;
    };
    if (parsed.error) return { summary: parsed.error, success: false };
    if (Array.isArray(parsed.updated_fields)) {
      return {
        summary:
          parsed.updated_fields.length > 0
            ? `Zaktualizowano profil: ${parsed.updated_fields.join(", ")}`
            : "Profil bez zmian",
        success: parsed.status !== "error",
      };
    }
    if (Array.isArray(parsed.results)) {
      const ok = parsed.results.filter((r) => r.status === "ok").length;
      const failed = parsed.results.length - ok;
      if (failed > 0) {
        return { summary: `Zapisano ${ok}, błędów: ${failed}`, success: false };
      }
      return { summary: ok === 1 ? "Zapisano wynik" : `Zapisano ${ok} wyników`, success: true };
    }
  } catch {
    // nie JSON — krótki skrót
  }
  return { summary: raw.length > 80 ? `${raw.slice(0, 77)}…` : raw, success: !raw.includes('"error"') };
}
