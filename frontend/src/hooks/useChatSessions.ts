import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { ChatMessage, ChatSession } from "@/types/api";

const SESSIONS_KEY = ["chat-sessions"] as const;
export const messagesKey = (sessionId: string) => ["chat-messages", sessionId] as const;

export function useChatSessions() {
  return useQuery({
    queryKey: SESSIONS_KEY,
    queryFn: () => apiFetch<ChatSession[]>("/api/v1/chat/sessions"),
  });
}

export function useChatMessages(sessionId: string | undefined) {
  return useQuery({
    queryKey: sessionId ? messagesKey(sessionId) : ["chat-messages", "none"],
    queryFn: () => apiFetch<ChatMessage[]>(`/api/v1/chat/sessions/${sessionId}/messages`),
    enabled: Boolean(sessionId),
  });
}

export interface CreateChatSessionInput {
  persona_id: string | null;
  title?: string;
}

export function useCreateChatSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateChatSessionInput) =>
      apiFetch<ChatSession>("/api/v1/chat/sessions", { method: "POST", body: input }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SESSIONS_KEY });
    },
  });
}

export function useUpdateChatSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sessionId, title }: { sessionId: string; title: string }) =>
      apiFetch<ChatSession>(`/api/v1/chat/sessions/${sessionId}`, {
        method: "PATCH",
        body: { title },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SESSIONS_KEY });
    },
  });
}

export function useDeleteChatSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiFetch<void>(`/api/v1/chat/sessions/${sessionId}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SESSIONS_KEY });
    },
  });
}
