import { Link, useLocation } from "react-router-dom";
import { Loader2, Square } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useChatTurnStore } from "@/store/useChatTurnStore";

/** Banner shown when a chat turn runs in the background (user on another tab). */
export function ChatTurnBanner() {
  const location = useLocation();
  const isStreaming = useChatTurnStore((s) => s.isStreaming);
  const sessionId = useChatTurnStore((s) => s.sessionId);
  const statusLabel = useChatTurnStore((s) => s.streaming?.statusLabel);
  const stopTurn = useChatTurnStore((s) => s.stopTurn);

  if (!isStreaming || !sessionId) return null;
  if (location.pathname === `/chat/${sessionId}`) return null;

  const detail = statusLabel?.trim();

  return (
    <Alert className="mx-auto mb-0 max-w-3xl rounded-none border-x-0 border-t-0">
      <Loader2 className="h-4 w-4 animate-spin" />
      <AlertDescription className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span>
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
        </span>
        <Button
          type="button"
          variant="destructive"
          size="sm"
          className="min-h-11"
          onClick={() => stopTurn(sessionId)}
        >
          <Square className="mr-1 h-3 w-3 fill-current" />
          Zatrzymaj
        </Button>
      </AlertDescription>
    </Alert>
  );
}
