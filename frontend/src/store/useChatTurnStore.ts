import { create } from "zustand";

import { stopChatTurn } from "@/lib/chat-turn-control";
import type { ConsultDetail } from "@/types/api";
import type { ChatStreamToolResultEvent } from "@/types/chat-stream";

export interface StreamingAssistantMessage {
  content: string;
  personaId: string | null;
  personaLabel: string | null;
  statusLabel: string | null;
  toolResults: ChatStreamToolResultEvent[];
  consultDetails: ConsultDetail[];
}

export interface ChatStreamError {
  message: string;
  canRetry: boolean;
}

interface PendingTurn {
  sessionId: string;
  content: string;
  sessionType: string;
  retry: boolean;
}

interface ChatTurnState {
  sessionId: string | null;
  sessionType: string;
  isStreaming: boolean;
  streaming: StreamingAssistantMessage | null;
  error: ChatStreamError | null;
  lastContent: string;
  pending: PendingTurn | null;
  /** Sessions with a turn running in the background (after navigating away from chat). */
  backgroundSessionIds: string[];
  queueTurn: (turn: PendingTurn) => void;
  stopTurn: (sessionId: string) => void;
  clearPending: () => void;
  setStreamingState: (patch: Partial<Pick<ChatTurnState, "isStreaming" | "streaming" | "error">>) => void;
  setLastContent: (content: string) => void;
  addBackgroundSession: (sessionId: string) => void;
  removeBackgroundSession: (sessionId: string) => void;
  resetForSession: (sessionId: string) => void;
}

export const useChatTurnStore = create<ChatTurnState>((set, get) => ({
  sessionId: null,
  sessionType: "persona",
  isStreaming: false,
  streaming: null,
  error: null,
  lastContent: "",
  pending: null,
  backgroundSessionIds: [],
  queueTurn: (turn) =>
    set({
      pending: turn,
      sessionId: turn.sessionId,
      sessionType: turn.sessionType,
      error: null,
    }),
  stopTurn: (sessionId) => {
    void stopChatTurn(sessionId);
  },
  clearPending: () => set({ pending: null }),
  setStreamingState: (patch) => set(patch),
  setLastContent: (content) => set({ lastContent: content }),
  addBackgroundSession: (sessionId) =>
    set((s) => ({
      backgroundSessionIds: s.backgroundSessionIds.includes(sessionId)
        ? s.backgroundSessionIds
        : [...s.backgroundSessionIds, sessionId],
    })),
  removeBackgroundSession: (sessionId) =>
    set((s) => ({
      backgroundSessionIds: s.backgroundSessionIds.filter((id) => id !== sessionId),
    })),
  resetForSession: (sessionId) => {
    const state = get();
    if (state.sessionId === sessionId && !state.isStreaming) {
      set({ sessionId: null, streaming: null, error: null });
    }
  },
}));
