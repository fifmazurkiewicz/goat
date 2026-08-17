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
 * `/chat` bez `:sessionId` na mobile — historia jako pełnoekranowy ekran listy
 * (spec 2026-08-17 GWT-2/GWT-3). Wcześniej lista żyła wyłącznie w zamkniętym `Sheet`,
 * którego trigger był w `ChatHeader` — niedostępny bez aktywnej sesji.
 */
export function ChatSessionsScreen(props: ChatSessionsScreenProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden pb-[env(safe-area-inset-bottom)]">
      <PersonaSessionDrawer {...props} />
    </div>
  );
}
