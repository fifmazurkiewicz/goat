import { PersonaSessionDrawer } from "@/components/chat/PersonaSessionDrawer";
import type { ChatSession, Persona } from "@/types/api";

interface ChatSessionsScreenProps {
  sessions: ChatSession[];
  personas: Persona[];
  activeSessionId: string | undefined;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onDeleteSession: (sessionId: string) => void;
}

/**
 * `/chat` without `:sessionId` on mobile — history rendered as a fullscreen list
 * screen (spec 2026-08-17 GWT-2/GWT-3). Previously the list lived only inside a closed
 * `Sheet` whose trigger lived in `ChatHeader` — unreachable without an active session.
 */
export function ChatSessionsScreen(props: ChatSessionsScreenProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden pb-[env(safe-area-inset-bottom)]">
      <PersonaSessionDrawer {...props} />
    </div>
  );
}
