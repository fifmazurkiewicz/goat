import { useCallback } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { ChatInput } from "@/components/chat/ChatInput";
import { MessageList } from "@/components/chat/MessageList";
import { useChatMessages } from "@/hooks/useChatSessions";
import { useChatStream } from "@/hooks/useChatStream";
import { useUsageLimitsStore } from "@/store/useUsageLimitsStore";
import { PERSONA_TYPE_LABELS } from "@/lib/persona-labels";
import type { ChatMessage, ChatSession, Persona } from "@/types/api";

interface ChatWindowProps {
  session: ChatSession;
  personas: Persona[];
  onOpenDrawer?: () => void;
}

/**
 * `ChatWindow` (smart) — JEDYNE miejsce otwierające/zamykające SSE (`useChatStream`),
 * docs/technical/frontend.md sekcja 4.
 */
export function ChatWindow({ session, personas, onOpenDrawer }: ChatWindowProps) {
  const { data: messages, isLoading } = useChatMessages(session.id);
  const { sendMessage, retry, clearError, isStreaming, streaming, error } = useChatStream(session.id, {
    sessionType: session.session_type,
  });
  const isNearLimit = useUsageLimitsStore((state) => state.isNearLimit);

  const activePersona = session.persona_id ? personas.find((p) => p.id === session.persona_id) ?? null : null;

  const personaLabelFor = useCallback(
    (message: ChatMessage) => {
      if (session.session_type !== "general" || !message.persona_id) return null;
      const persona = personas.find((p) => p.id === message.persona_id);
      return persona ? `${persona.name} · ${PERSONA_TYPE_LABELS[persona.type]}` : null;
    },
    [personas, session.session_type]
  );

  const isBudgetExceeded = Boolean(error && !error.canRetry);
  const disabled = isStreaming || isBudgetExceeded;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <ChatHeader session={session} persona={activePersona} onOpenDrawer={onOpenDrawer} />

      {isLoading ? (
        <div className="min-h-0 flex-1 overflow-y-auto p-6 text-sm text-muted-foreground">Ładowanie historii…</div>
      ) : (
        <MessageList messages={messages ?? []} personaLabelFor={personaLabelFor} streaming={streaming} />
      )}

      {isNearLimit && !error ? (
        <Alert variant="warning" className="mx-4 mb-2 shrink-0">
          <AlertDescription>Zbliżasz się do limitu budżetu na tym koncie.</AlertDescription>
        </Alert>
      ) : null}

      {error ? (
        <Alert variant={isBudgetExceeded ? "destructive" : "warning"} className="mx-4 mb-2 shrink-0">
          <AlertTitle>{isBudgetExceeded ? "Limit budżetu osiągnięty" : "Połączenie przerwane"}</AlertTitle>
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>{error.message}</span>
            <span className="flex gap-2">
              {error.canRetry ? (
                <Button type="button" size="sm" variant="outline" onClick={retry}>
                  Wyślij ponownie
                </Button>
              ) : (
                <a href="mailto:admin@example.com" className="text-sm underline underline-offset-2">
                  Poproś administratora o zwiększenie budżetu
                </a>
              )}
              <Button type="button" size="sm" variant="ghost" onClick={clearError}>
                Zamknij
              </Button>
            </span>
          </AlertDescription>
        </Alert>
      ) : null}

      <ChatInput
        onSend={sendMessage}
        disabled={disabled}
        disabledReason={isStreaming ? "Trwa odpowiedź…" : isBudgetExceeded ? "Limit budżetu osiągnięty." : undefined}
        showSlashAutocomplete={session.session_type === "general"}
        activePersonas={personas.filter((p) => p.active)}
      />
    </div>
  );
}
