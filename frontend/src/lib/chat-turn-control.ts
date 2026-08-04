import { apiFetch } from "@/lib/api-client";

const abortControllers = new Map<string, AbortController>();

/** Rejestruje AbortController bieżącej tury (useChatTurnRunner). */
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

/** Zamyka SSE i prosi backend o anulowanie orkiestratora. */
export async function stopChatTurn(sessionId: string): Promise<void> {
  abortLocalChatTurn(sessionId);
  try {
    await apiFetch(`/api/v1/chat/sessions/${sessionId}/cancel`, { method: "POST" });
  } catch {
    // Tura mogła się już zakończyć albo abort zamknął połączenie przed odpowiedzią.
  }
}
