import { Menu, MessageSquarePlus } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { personaAvatarColor, personaInitials } from "@/lib/persona-labels";
import { sessionDisplayTitle } from "@/lib/chat-session";
import type { ChatSession, Persona } from "@/types/api";

interface ChatHeaderProps {
  session: ChatSession;
  persona: Persona | null;
  onOpenDrawer?: () => void;
  onNewSession?: () => void;
}

/** Cienki pasek sesji — bez dokumentacji w UI, żeby historia miała miejsce. */
export function ChatHeader({ session, persona, onOpenDrawer, onNewSession }: ChatHeaderProps) {
  const title =
    session.session_type === "persona" && persona
      ? persona.name
      : sessionDisplayTitle(session, "Ogólna rozmowa");
  const subtitle =
    session.session_type === "persona" ? sessionDisplayTitle(session, "Rozmowa 1:1") : null;

  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-b px-2 py-2 sm:px-4 sm:py-3">
      <div className="flex min-w-0 items-center gap-2 sm:gap-3">
        {onOpenDrawer ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="min-h-11 min-w-11 shrink-0 md:hidden"
            onClick={onOpenDrawer}
            aria-label="Lista rozmów"
          >
            <Menu className="h-5 w-5" />
          </Button>
        ) : null}
        {session.session_type === "persona" && persona ? (
          <Avatar className="h-9 w-9 shrink-0">
            <AvatarFallback className={`${personaAvatarColor(persona.id)} text-white`}>
              {personaInitials(persona.name)}
            </AvatarFallback>
          </Avatar>
        ) : null}
        <div className="min-w-0">
          <div className="truncate font-semibold leading-tight">{title}</div>
          {subtitle && subtitle !== title ? (
            <div className="truncate text-xs text-muted-foreground">{subtitle}</div>
          ) : null}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {session.session_type === "general" ? (
          <Badge variant="outline" className="hidden sm:inline-flex">
            Goat · Kierownik
          </Badge>
        ) : null}
        {onNewSession ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="min-h-11 min-w-11 md:hidden"
            onClick={onNewSession}
            aria-label="Nowa rozmowa"
          >
            <MessageSquarePlus className="h-5 w-5" />
          </Button>
        ) : null}
      </div>
    </div>
  );
}
