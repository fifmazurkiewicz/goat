import { useLayoutEffect, useMemo, useRef } from "react";

import { ConsultDetails } from "@/components/chat/ConsultDetails";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { StreamingStatusLine } from "@/components/chat/StreamingStatusLine";
import { ToolResultChip } from "@/components/chat/ToolResultChip";
import type { StreamingAssistantMessage } from "@/hooks/useChatStream";
import { visibleChatMessages } from "@/lib/chat-messages";
import type { ChatMessage } from "@/types/api";
import type { ChatStreamToolResultEvent } from "@/types/chat-stream";

type Row =
  | { kind: "chat"; key: string; message: ChatMessage; personaLabel: string | null }
  | { kind: "streaming-tool"; key: string; event: ChatStreamToolResultEvent }
  | { kind: "streaming-status"; key: string; label: string }
  | { kind: "streaming-text"; key: string; content: string; personaLabel: string | null; consultDetails?: StreamingAssistantMessage["consultDetails"] };

interface MessageListProps {
  messages: ChatMessage[];
  personaLabelFor: (message: ChatMessage) => string | null;
  streaming: StreamingAssistantMessage | null;
}

/**
 * `MessageList` — history rendered directly in the DOM (a typical coaching session
 * does not need virtualization). A bottom anchor (`chat-history-end`) keeps the most
 * recent messages visible. `aria-live="polite"` only on the streaming message.
 */
export function MessageList({ messages, personaLabelFor, streaming }: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);

  const rows = useMemo<Row[]>(() => {
    const visible = visibleChatMessages(messages);
    const chatRows: Row[] = visible.map((message) => ({
      kind: "chat",
      key: message.id,
      message,
      personaLabel: message.role === "assistant" ? personaLabelFor(message) : null,
    }));

    if (!streaming) return chatRows;

    const streamingRows: Row[] = streaming.toolResults.map((event, index) => ({
      kind: "streaming-tool",
      key: `streaming-tool-${index}`,
      event,
    }));

    if (streaming.content || streaming.personaLabel) {
      streamingRows.push({
        kind: "streaming-text",
        key: "streaming-text",
        content: streaming.content,
        personaLabel: streaming.personaLabel,
        consultDetails: streaming.consultDetails,
      });
    }
    // A model may emit a short pre-tool sentence ("Zapisuję…") before a slow
    // operation. Keep the live phase visible instead of making the UI look frozen.
    if (streaming.statusLabel) {
      streamingRows.push({
        kind: "streaming-status",
        key: "streaming-status",
        label: streaming.statusLabel,
      });
    }

    return [...chatRows, ...streamingRows];
  }, [messages, personaLabelFor, streaming]);

  useLayoutEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [rows.length, streaming?.content, streaming?.statusLabel]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-3 sm:px-6">
      {rows.map((row) => (
        <div key={row.key} className="pb-4">
          {row.kind === "chat" && (
            <>
              <MessageBubble message={row.message} personaLabel={row.personaLabel} />
              {row.message.consultDetails?.length ? (
                <ConsultDetails details={row.message.consultDetails} className="mt-1" />
              ) : null}
            </>
          )}
          {row.kind === "streaming-tool" && <ToolResultChip {...row.event} />}
          {row.kind === "streaming-status" && <StreamingStatusLine label={row.label} />}
          {row.kind === "streaming-text" && (
            <div aria-live="polite">
              <MessageBubble message={{ role: "assistant", content: row.content }} personaLabel={row.personaLabel} />
              {row.consultDetails?.length ? (
                <ConsultDetails details={row.consultDetails} className="mt-1" />
              ) : null}
            </div>
          )}
        </div>
      ))}
      {rows.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          Napisz pierwszą wiadomość, żeby zacząć rozmowę.
        </p>
      ) : null}
      <div ref={endRef} data-testid="chat-history-end" className="h-px w-full shrink-0" aria-hidden />
    </div>
  );
}
