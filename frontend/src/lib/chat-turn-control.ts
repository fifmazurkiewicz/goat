import { apiFetch } from "@/lib/api-client";

const abortControllers = new Map<string, AbortController>();

/** Registers the AbortController of the current turn (useChatTurnRunner). */
export function registerChatTurnAbort(sessionId: string, controller: AbortController): void {
  abortControllers.set(sessionId, controller);
}

export function unregisterChatTurnAbort(sessionId: string): void {
  abortControllers.delete(sessionId);
}

function abortLocalChatTurn(sessionId: string): boolean {
  const controller = abortControllers.get(sessionId);
  if (controller == null) return false;
  controller.abort();
  return true;
}

/** Closes the SSE and asks the backend to cancel the orchestrator. */
export async function stopChatTurn(sessionId: string): Promise<void> {
  abortLocalChatTurn(sessionId);
  try {
    await apiFetch(`/api/v1/chat/sessions/${sessionId}/cancel`, { method: "POST" });
  } catch {
    // The turn may have already finished, or the abort closed the connection before the response.
  }
}
