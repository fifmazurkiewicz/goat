import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageSquarePlus, PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { ChatSessionsScreen } from "@/components/chat/ChatSessionsScreen";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { NewSessionDialog } from "@/components/chat/NewSessionDialog";
import { PersonaSessionDrawer } from "@/components/chat/PersonaSessionDrawer";
import { useChatSessions, useDeleteChatSession, useUpdateChatSession } from "@/hooks/useChatSessions";
import { useLocalStorageState } from "@/hooks/useLocalStorageState";
import { useIsMobile } from "@/hooks/useMediaQuery";
import { usePersonas } from "@/hooks/usePersonas";
import { latestSessionId } from "@/lib/chat-session";

interface ChatLayoutProps {
  sessionId: string | undefined;
}

/**
 * `ChatLayout` (smart) — drawer open/closed (localStorage), URL sync sessionId
 * (docs/technical/frontend.md section 4). Height = `flex-1 min-h-0` in AppShell (`h-dvh`);
 * scroll only in MessageList / session list — the "Send" input is always visible.
 *
 * Mobile (spec 2026-08-17): `/chat` without `:sessionId` = conversation list screen; on
 * the first app entry it auto-jumps to the most recent conversation (after that the user
 * can return to the list without being redirected again).
 */
export function ChatLayout({ sessionId }: ChatLayoutProps) {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [isDrawerOpen, setIsDrawerOpen] = useLocalStorageState("coach.chat.drawerOpen", true);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [isNewSessionOpen, setIsNewSessionOpen] = useState(false);
  const didAutoOpenRef = useRef(false);

  const { data: sessions } = useChatSessions();
  const updateSession = useUpdateChatSession();
  const deleteSession = useDeleteChatSession();
  const { data: personasData } = usePersonas();
  const personas = personasData?.items ?? [];
  const activeSession = sessions?.find((s) => s.id === sessionId);

  // GWT-1: one-time auto-entry into the latest conversation (mobile only — on desktop
  // the list is always visible, so a redirect would be surprising).
  useEffect(() => {
    if (!isMobile || sessionId || didAutoOpenRef.current || !sessions) return;
    const latest = latestSessionId(sessions);
    didAutoOpenRef.current = true;
    if (latest) navigate(`/chat/${latest}`, { replace: true });
  }, [isMobile, sessionId, sessions, navigate]);

  function handleSelectSession(id: string) {
    navigate(`/chat/${id}`);
    setIsMobileDrawerOpen(false);
  }

  function handleDeleteSession(id: string) {
    deleteSession.mutate(id, {
      onSuccess: () => {
        if (sessionId === id) {
          // After deletion the user should stay on the list, not be pulled into another conversation.
          didAutoOpenRef.current = true;
          navigate("/chat");
        }
      },
    });
  }

  const drawerProps = {
    sessions: sessions ?? [],
    personas,
    activeSessionId: sessionId,
    onSelectSession: handleSelectSession,
    onNewSession: () => setIsNewSessionOpen(true),
    onRenameSession: (id: string, title: string) => updateSession.mutate({ sessionId: id, title }),
    onDeleteSession: handleDeleteSession,
  };

  const drawer = <PersonaSessionDrawer {...drawerProps} />;

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden">
      {!isMobile && isDrawerOpen ? (
        <div className="flex min-h-0 w-72 shrink-0 flex-col overflow-hidden border-r">{drawer}</div>
      ) : null}

      {isMobile ? (
        <Sheet open={isMobileDrawerOpen} onOpenChange={setIsMobileDrawerOpen}>
          <SheetContent side="left" className="w-[min(20rem,100%)] p-0 pt-[env(safe-area-inset-top)]">
            <SheetTitle className="sr-only">Rozmowy</SheetTitle>
            {drawer}
          </SheetContent>
        </Sheet>
      ) : null}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {!isMobile ? (
          <div className="flex shrink-0 items-center border-b px-2 py-1">
            <Button type="button" variant="ghost" size="icon" onClick={() => setIsDrawerOpen((v) => !v)}>
              {isDrawerOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsNewSessionOpen(true)}>
              <MessageSquarePlus className="mr-1 h-4 w-4" /> Nowa rozmowa
            </Button>
          </div>
        ) : null}

        {activeSession ? (
          <ChatWindow
            key={activeSession.id}
            session={activeSession}
            personas={personas}
            onOpenDrawer={isMobile ? () => setIsMobileDrawerOpen(true) : undefined}
            onNewSession={isMobile ? () => setIsNewSessionOpen(true) : undefined}
          />
        ) : isMobile ? (
          <ChatSessionsScreen {...drawerProps} />
        ) : (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 overflow-y-auto p-6 text-center">
            <p className="text-muted-foreground">Wybierz rozmowę z listy albo zacznij nową.</p>
            <Button type="button" onClick={() => setIsNewSessionOpen(true)}>
              <MessageSquarePlus className="mr-1 h-4 w-4" /> Nowa rozmowa
            </Button>
          </div>
        )}
      </div>

      <NewSessionDialog
        open={isNewSessionOpen}
        onOpenChange={setIsNewSessionOpen}
        personas={personas}
        onCreated={(id) => navigate(`/chat/${id}`)}
      />
    </div>
  );
}
