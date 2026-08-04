import { useMemo } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SessionListItem } from "@/components/chat/SessionListItem";
import { PERSONA_TYPE_LABELS } from "@/lib/persona-labels";
import type { ChatSession, Persona } from "@/types/api";

interface PersonaSessionDrawerProps {
  sessions: ChatSession[];
  personas: Persona[];
  activeSessionId: string | undefined;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
}

interface SessionGroup {
  key: string;
  label: string;
  sessions: ChatSession[];
}

/** Collapsible od startu (Sheet z shadcn na mobile), docs/technical/frontend.md sekcja 4. */
export function PersonaSessionDrawer({
  sessions,
  personas,
  activeSessionId,
  onSelectSession,
  onNewSession,
}: PersonaSessionDrawerProps) {
  const groups = useMemo<SessionGroup[]>(() => {
    const uniqueSessions = Array.from(new Map(sessions.map((s) => [s.id, s])).values());
    const generalSessions = uniqueSessions.filter((s) => s.session_type === "general");
    const personaGroups = personas
      .map((persona) => ({
        key: persona.id,
        label: `${persona.name} · ${PERSONA_TYPE_LABELS[persona.type]}`,
        sessions: uniqueSessions.filter((s) => s.session_type === "persona" && s.persona_id === persona.id),
      }))
      .filter((group) => group.sessions.length > 0);

    const result: SessionGroup[] = [];
    if (generalSessions.length > 0) {
      result.push({ key: "general", label: "Ogólne", sessions: generalSessions });
    }
    return [...result, ...personaGroups];
  }, [sessions, personas]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-4">
      <h2 className="shrink-0 text-lg font-semibold">Rozmowy</h2>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto">
        {groups.map((group) => (
          <div key={group.key}>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-accent-foreground/70">
              {group.label}
            </div>
            <div className="space-y-1">
              {group.sessions.map((session) => (
                <SessionListItem
                  key={session.id}
                  session={session}
                  isActive={session.id === activeSessionId}
                  onSelect={() => onSelectSession(session.id)}
                />
              ))}
            </div>
          </div>
        ))}
        {groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">Brak rozmów — zacznij nową poniżej.</p>
        ) : null}
      </div>
      <Button type="button" variant="ghost" className="shrink-0 justify-start px-0" onClick={onNewSession}>
        <Plus className="mr-1 h-4 w-4" /> Nowa rozmowa
      </Button>
    </div>
  );
}
