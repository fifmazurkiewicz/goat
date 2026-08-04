import { useCallback, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { ChatInput } from "@/components/chat/ChatInput";
import { MessageList } from "@/components/chat/MessageList";
import { useChatMessages } from "@/hooks/useChatSessions";
import { useChatStream } from "@/hooks/useChatStream";
import { useUsageLimitsStore } from "@/store/useUsageLimitsStore";
import { formatPersonaDisplayLabel } from "@/lib/persona-labels";
import { TEAM_LEAD_DISPLAY_LABEL } from "@/lib/team-lead";
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
  const location = useLocation();
  const navigate = useNavigate();
  const autoSendDoneRef = useRef(false);
  const { data: messages, isLoading } = useChatMessages(session.id);
  const { sendMessage, retry, stopGeneration, clearError, isStreaming, streaming, error } = useChatStream(session.id, {
    sessionType: session.session_type,
  });
  const isNearLimit = useUsageLimitsStore((state) => state.isNearLimit);

  useEffect(() => {
    autoSendDoneRef.current = false;
  }, [session.id]);

  useEffect(() => {
    const state = location.state as { autoSend?: string } | null;
    const autoSend = state?.autoSend?.trim();
    if (!autoSend || autoSendDoneRef.current || isStreaming || isLoading) return;
    autoSendDoneRef.current = true;
    sendMessage(autoSend);
    navigate(location.pathname, { replace: true, state: {} });
  }, [location.pathname, location.state, isStreaming, isLoading, sendMessage, navigate]);

  const activePersona = session.persona_id ? personas.find((p) => p.id === session.persona_id) ?? null : null;

  const personaLabelFor = useCallback(
    (message: ChatMessage) => {
      if (session.session_type !== "general") return null;
      if (message.role !== "assistant") return null;
      // Bezpośrednia rozmowa z personą — tylko /slug (assistant ma persona_id).
      if (message.persona_id) {
        const persona = personas.find((p) => p.id === message.persona_id);
        return persona ? formatPersonaDisplayLabel(persona.name, persona.type) : null;
      }
      return TEAM_LEAD_DISPLAY_LABEL;
    },
    [personas, session.session_type]
  );

  const isBudgetExceeded = Boolean(error && !error.canRetry);
  const inputDisabled = isBudgetExceeded;

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
        onStop={stopGeneration}
        isStreaming={isStreaming}
        disabled={inputDisabled}
        disabledReason={isBudgetExceeded ? "Limit budżetu osiągnięty." : undefined}
        showSlashAutocomplete={session.session_type === "general"}
        activePersonas={personas.filter((p) => p.active)}
      />
    </div>
  );
}
