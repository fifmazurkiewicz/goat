import { format } from "date-fns";
import { pl } from "date-fns/locale";

import { cn } from "@/lib/utils";
import type { ChatSession } from "@/types/api";

interface SessionListItemProps {
  session: ChatSession;
  isActive: boolean;
  onSelect: () => void;
}

/** Avatar/kolor persony to silne kodowanie wizualne na poziomie grupy (nagłówek), nie tutaj. */
export function SessionListItem({ session, isActive, onSelect }: SessionListItemProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-md px-2 py-2 text-left transition-colors hover:bg-accent",
        isActive && "bg-accent text-accent-foreground"
      )}
    >
      <div className="flex items-center gap-1.5">
        <span className="truncate text-sm">{session.title ?? "Nowa rozmowa"}</span>
        {session.session_type === "general" ? (
          <span className="shrink-0 rounded-full bg-accent px-1.5 py-0.5 text-[10px] font-medium">Auto</span>
        ) : null}
      </div>
      <div className="mt-0.5 text-xs text-muted-foreground">
        {format(new Date(session.updated_at), "d MMM, HH:mm", { locale: pl })}
      </div>
    </button>
  );
}
