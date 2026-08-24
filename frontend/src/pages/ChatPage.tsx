import { useParams } from "react-router-dom";

import { ChatLayout } from "@/components/chat/ChatLayout";

/**
 * `/chat` and `/chat/:sessionId` — 'persona' (1:1) and 'general' (auto-routing,
 * ADR-13) sessions. Structure: docs/technical/frontend.md section 4.
 */
export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <ChatLayout sessionId={sessionId} />
    </div>
  );
}
