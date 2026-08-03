import { Menu } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { personaAvatarColor, personaInitials } from "@/lib/persona-labels";
import type { ChatSession, Persona } from "@/types/api";

interface ChatHeaderProps {
  session: ChatSession;
  persona: Persona | null;
  onOpenDrawer?: () => void;
}

/** Avatar/kolor/nazwa aktywnej persony (docs/technical/frontend.md sekcja 4). */
export function ChatHeader({ session, persona, onOpenDrawer }: ChatHeaderProps) {
  return (
    <div className="flex items-center justify-between gap-2 border-b p-4">
      <div className="flex items-center gap-3">
        {onOpenDrawer ? (
          <Button type="button" variant="ghost" size="icon" className="md:hidden" onClick={onOpenDrawer}>
            <Menu className="h-5 w-5" />
          </Button>
        ) : null}
        {session.session_type === "persona" && persona ? (
          <>
            <Avatar className="h-9 w-9">
              <AvatarFallback className={`${personaAvatarColor(persona.id)} text-white`}>
                {personaInitials(persona.name)}
              </AvatarFallback>
            </Avatar>
            <div>
              <div className="font-semibold leading-tight">{persona.name}</div>
              <div className="text-xs text-muted-foreground">{session.title ?? "Rozmowa 1:1"}</div>
            </div>
          </>
        ) : (
          <div>
            <div className="font-semibold leading-tight">{session.title ?? "Ogólna rozmowa"}</div>
            <div className="text-xs text-muted-foreground">Odpowiada właściwy trener wg tematu pytania</div>
          </div>
        )}
      </div>
      {session.session_type === "general" ? <Badge variant="outline">Auto-routing</Badge> : null}
    </div>
  );
}
