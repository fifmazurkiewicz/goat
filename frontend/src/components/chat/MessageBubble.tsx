import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/api";

interface MessageBubbleProps {
  message: Pick<ChatMessage, "role" | "content">;
  /** W sesji 'general' pokazujemy nagłówek persona_label nad odpowiedzią (ADR-13);
   * w sesji 'persona' pomijany (kontekst już wiadomy z ChatHeader). */
  personaLabel?: string | null;
}

export function MessageBubble({ message, personaLabel }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex max-w-[80%] flex-col gap-1", isUser ? "self-end items-end" : "self-start items-start")}>
      {!isUser && personaLabel ? <div className="text-xs font-medium text-accent-foreground/80">{personaLabel}</div> : null}
      <div
        className={cn(
          "rounded-lg border px-3 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-accent/40"
        )}
      >
        <p className="whitespace-pre-line">{message.content}</p>
      </div>
    </div>
  );
}
