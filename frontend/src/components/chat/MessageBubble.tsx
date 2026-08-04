import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/api";

interface MessageBubbleProps {
  message: Pick<ChatMessage, "role" | "content">;
  /** W sesji 'general' pokazujemy nagłówek persona_label nad odpowiedzią (ADR-13);
   * w sesji 'persona' pomijany (kontekst już wiadomy z ChatHeader). */
  personaLabel?: string | null;
}

/**
 * Bubble wiadomości — treść asystenta/usera jako Markdown (pogrubienie, listy, akapity).
 * Bez `rehype-raw`: tylko bezpieczny subset MD, bez HTML z modelu.
 */
export function MessageBubble({ message, personaLabel }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const content = message.content ?? "";

  return (
    <div className={cn("flex max-w-[80%] flex-col gap-1", isUser ? "self-end items-end" : "self-start items-start")}>
      {!isUser && personaLabel ? <div className="text-xs font-medium text-accent-foreground/80">{personaLabel}</div> : null}
      <div
        className={cn(
          "rounded-lg border px-3 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-accent/40"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-line">{content}</p>
        ) : (
          <div
            className={cn(
              "chat-md leading-relaxed",
              "[&_p]:mb-2 [&_p:last-child]:mb-0",
              "[&_ul]:mb-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:marker:text-muted-foreground",
              "[&_ol]:mb-2 [&_ol]:list-decimal [&_ol]:pl-5",
              "[&_li]:my-0.5 [&_li>p]:mb-0",
              "[&_strong]:font-semibold [&_em]:italic",
              "[&_a]:underline",
              "[&_h1]:mb-2 [&_h1]:mt-1 [&_h1]:text-base [&_h1]:font-semibold",
              "[&_h2]:mb-2 [&_h2]:mt-2 [&_h2]:text-sm [&_h2]:font-semibold [&_h2:first-child]:mt-0",
              "[&_h3]:mb-1.5 [&_h3]:mt-1.5 [&_h3]:text-sm [&_h3]:font-semibold",
              "[&_blockquote]:mb-2 [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground"
            )}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              components={{
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noreferrer noopener">
                    {children}
                  </a>
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
