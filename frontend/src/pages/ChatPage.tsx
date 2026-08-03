import { useParams } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Docelowa struktura (docs/technical/frontend.md sekcja 4):
 * ChatLayout > PersonaSessionDrawer + ChatHeader + ChatWindow (SSE przez
 * `useChatStream`, MessageList wirtualizowana, ChatInput). TODO: kolejny
 * etap — SSE streaming realnych tokenów (`streamChatMessage`, sekcja 3).
 */
export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  return (
    <div className="container py-10">
      <Card>
        <CardHeader>
          <CardTitle>Czat</CardTitle>
          <CardDescription>
            {sessionId
              ? `Tu pojawi się okno rozmowy dla sesji ${sessionId}.`
              : "Tu pojawi się lista sesji czatu i okno rozmowy ze streamingiem SSE (token po tokenie)."}
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">TODO: kolejny etap.</CardContent>
      </Card>
    </div>
  );
}
