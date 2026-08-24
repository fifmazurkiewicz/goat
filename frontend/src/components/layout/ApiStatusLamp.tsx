import { useState } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { type ApiHealthLampState, lampMessage } from "@/lib/api-health";
import { cn } from "@/lib/utils";

interface ApiStatusLampProps {
  lamp: ApiHealthLampState;
  onRetry?: () => void;
}

/**
 * API status dot — only when the backend is waking up or down (ADR-19).
 * Hover/tap shows a short text. After the backend is awake the parent passes `hidden`.
 */
export function ApiStatusLamp({ lamp, onRetry }: ApiStatusLampProps) {
  const [open, setOpen] = useState(false);
  const message = lampMessage(lamp);
  if (lamp === "hidden" || !message) return null;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center"
          aria-label={message}
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
          onClick={() => {
            if (lamp === "down") onRetry?.();
          }}
        >
          <span
            role="status"
            aria-live="polite"
            className={cn(
              "h-2.5 w-2.5 rounded-full",
              lamp === "waking" ? "animate-pulse bg-amber-400" : "bg-red-500"
            )}
          />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-auto max-w-xs p-3 text-sm"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {message}
      </PopoverContent>
    </Popover>
  );
}
