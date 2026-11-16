import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/api";

interface MessageBubbleProps {
  message: Pick<ChatMessage, "role" | "content">;
  /** In a 'general' session we show the persona_label header above the reply (ADR-13);
   * in a 'persona' session it's omitted (the context is already clear from ChatHeader). */
  personaLabel?: string | null;
  /** Live (still streaming) reply — hides the copy action until the text is final. */
  streaming?: boolean;
}

const COPIED_FEEDBACK_MS = 2000;

/** Copies the raw Markdown of an assistant reply to the clipboard (Polish UI copy). */
function CopyMessageButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), COPIED_FEEDBACK_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      toast.error("Nie udało się skopiować wiadomości.");
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? "Skopiowano wiadomość" : "Kopiuj wiadomość"}
      className={cn(
        "inline-flex min-h-11 min-w-11 items-center justify-center gap-1 rounded-md px-2 text-[11px] text-muted-foreground",
        "transition-colors hover:bg-accent hover:text-accent-foreground motion-reduce:transition-none",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-8 sm:min-w-8"
      )}
    >
      {copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
      <span>{copied ? "Skopiowano" : "Kopiuj"}</span>
    </button>
  );
}

/**
 * Message bubble — assistant/user content rendered as Markdown (bold, lists, paragraphs).
 * No `rehype-raw`: only a safe MD subset, no HTML from the model.
 */
export function MessageBubble({ message, personaLabel, streaming = false }: MessageBubbleProps) {
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
      {!isUser ? (
        <div className="flex items-center gap-1 px-1">
          <span className="text-[10px] text-muted-foreground">Wygenerowane przez AI</span>
          {!streaming && content.trim() ? <CopyMessageButton text={content} /> : null}
        </div>
      ) : null}
    </div>
  );
}
