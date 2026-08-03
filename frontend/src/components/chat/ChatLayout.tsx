import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageSquarePlus, PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { NewSessionDialog } from "@/components/chat/NewSessionDialog";
import { PersonaSessionDrawer } from "@/components/chat/PersonaSessionDrawer";
import { useChatSessions } from "@/hooks/useChatSessions";
import { useLocalStorageState } from "@/hooks/useLocalStorageState";
import { useIsMobile } from "@/hooks/useMediaQuery";
import { usePersonas } from "@/hooks/usePersonas";

interface ChatLayoutProps {
  sessionId: string | undefined;
}

/**
 * `ChatLayout` (smart) — drawer open/closed (localStorage), URL sync sessionId
 * (docs/technical/frontend.md sekcja 4).
 */
export function ChatLayout({ sessionId }: ChatLayoutProps) {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [isDrawerOpen, setIsDrawerOpen] = useLocalStorageState("coach.chat.drawerOpen", true);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [isNewSessionOpen, setIsNewSessionOpen] = useState(false);

  const { data: sessions } = useChatSessions();
  const { data: personasData } = usePersonas();
  const personas = personasData?.items ?? [];
  const activeSession = sessions?.find((s) => s.id === sessionId);

  function handleSelectSession(id: string) {
    navigate(`/chat/${id}`);
    setIsMobileDrawerOpen(false);
  }

  const drawer = (
    <PersonaSessionDrawer
      sessions={sessions ?? []}
      personas={personas}
      activeSessionId={sessionId}
      onSelectSession={handleSelectSession}
      onNewSession={() => setIsNewSessionOpen(true)}
    />
  );

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {!isMobile && isDrawerOpen ? <div className="w-72 shrink-0 border-r">{drawer}</div> : null}

      {isMobile ? (
        <Sheet open={isMobileDrawerOpen} onOpenChange={setIsMobileDrawerOpen}>
          <SheetContent side="left" className="w-80 p-0">
            <SheetTitle className="sr-only">Rozmowy</SheetTitle>
            {drawer}
          </SheetContent>
        </Sheet>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        {!isMobile ? (
          <div className="flex items-center border-b px-2 py-1">
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
          />
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
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
