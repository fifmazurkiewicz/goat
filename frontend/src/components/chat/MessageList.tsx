import { useEffect, useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

import { MessageBubble } from "@/components/chat/MessageBubble";
import { ToolResultChip } from "@/components/chat/ToolResultChip";
import type { StreamingAssistantMessage } from "@/hooks/useChatStream";
import type { ChatMessage } from "@/types/api";
import type { ChatStreamToolResultEvent } from "@/types/chat-stream";

type Row =
  | { kind: "chat"; key: string; message: ChatMessage; personaLabel: string | null }
  | { kind: "streaming-tool"; key: string; event: ChatStreamToolResultEvent }
  | { kind: "streaming-text"; key: string; content: string; personaLabel: string | null };

interface MessageListProps {
  messages: ChatMessage[];
  personaLabelFor: (message: ChatMessage) => string | null;
  streaming: StreamingAssistantMessage | null;
}

/**
 * `MessageList` (dumb, wirtualizowana przy długiej historii — `@tanstack/react-virtual`,
 * docs/technical/frontend.md sekcja 4). `aria-live="polite"` na kontenerze streamującej
 * wiadomości, nie na całej liście.
 */
export function MessageList({ messages, personaLabelFor, streaming }: MessageListProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const rows = useMemo<Row[]>(() => {
    const chatRows: Row[] = messages.map((message) => ({
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
      });
    }

    return [...chatRows, ...streamingRows];
  }, [messages, personaLabelFor, streaming]);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 88,
    overscan: 8,
  });

  useEffect(() => {
    if (rows.length === 0) return;
    virtualizer.scrollToIndex(rows.length - 1, { align: "end" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows.length, streaming?.content]);

  return (
    <div ref={parentRef} className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const row = rows[virtualRow.index];
          return (
            <div
              key={row.key}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start}px)`,
              }}
              className="flex flex-col pb-4"
            >
              {row.kind === "chat" && <MessageBubble message={row.message} personaLabel={row.personaLabel} />}
              {row.kind === "streaming-tool" && <ToolResultChip {...row.event} />}
              {row.kind === "streaming-text" && (
                <div aria-live="polite">
                  <MessageBubble message={{ role: "assistant", content: row.content }} personaLabel={row.personaLabel} />
                </div>
              )}
            </div>
          );
        })}
      </div>
      {rows.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          Napisz pierwszą wiadomość, żeby zacząć rozmowę.
        </p>
      ) : null}
    </div>
  );
}
