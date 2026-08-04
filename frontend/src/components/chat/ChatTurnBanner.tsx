import { Link, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { useChatTurnStore } from "@/store/useChatTurnStore";

/** Banner gdy tura czatu trwa w tle (user na innej zakładce). */
export function ChatTurnBanner() {
  const location = useLocation();
  const isStreaming = useChatTurnStore((s) => s.isStreaming);
  const sessionId = useChatTurnStore((s) => s.sessionId);
  const statusLabel = useChatTurnStore((s) => s.streaming?.statusLabel);

  if (!isStreaming || !sessionId) return null;
  if (location.pathname === `/chat/${sessionId}`) return null;

  const detail = statusLabel?.trim();

  return (
    <Alert className="mx-auto mb-0 max-w-3xl rounded-none border-x-0 border-t-0">
      <Loader2 className="h-4 w-4 animate-spin" />
      <AlertDescription>
        {detail ? (
          <>
            <span className="font-medium">{detail}</span>
            {" — "}
          </>
        ) : null}
        Możesz wrócić do{" "}
        <Link to={`/chat/${sessionId}`} className="font-medium underline underline-offset-2">
          czatu
        </Link>
        ; praca kontynuuje w tle.
      </AlertDescription>
    </Alert>
  );
}
