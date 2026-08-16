import { useParams } from "react-router-dom";

import { ChatLayout } from "@/components/chat/ChatLayout";

/**
 * `/chat` i `/chat/:sessionId` — sesje 'persona' (1:1) i 'general' (auto-routing,
 * ADR-13). Struktura: docs/technical/frontend.md sekcja 4.
 */
export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <ChatLayout sessionId={sessionId} />
    </div>
  );
}
