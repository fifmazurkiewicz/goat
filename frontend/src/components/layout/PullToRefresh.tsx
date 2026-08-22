import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

import { PULL_THRESHOLD_PX, usePullToRefresh } from "@/hooks/usePullToRefresh";
import { useChatTurnStore } from "@/store/useChatTurnStore";
import { cn } from "@/lib/utils";

interface PullToRefreshProps {
  children: ReactNode;
  className?: string;
}

/**
 * Wrapper pull-to-refresh (mobile, spec 2026-08-22) — wskaźnik wysuwa się NAD treścią
 * (transform, bez layout shift). Montowany w AppShell wokół `<Outlet />`, więc działa
 * na wszystkich ekranach. `data-pull-to-refresh` kończy łańcuch scrollerów w hooku.
 * Gest zablokowany gdy tura czatu streamuje się w tle — nie przerywamy SSE.
 */
export function PullToRefresh({ children, className }: PullToRefreshProps) {
  const queryClient = useQueryClient();
  const isStreaming = useChatTurnStore((s) => s.isStreaming);
  const { pullDistance, isRefreshing, containerRef, handlers } = usePullToRefresh({
    isLocked: isStreaming,
    threshold: PULL_THRESHOLD_PX,
    onRefresh: () =>
      queryClient.invalidateQueries({ refetchType: "active" }),
  });
  const indicatorVisible = pullDistance > 0 || isRefreshing;
  const progress = Math.min(pullDistance / PULL_THRESHOLD_PX, 1);

  return (
    <div
      ref={containerRef}
      data-pull-to-refresh=""
      className={cn("relative flex min-h-0 flex-1 flex-col overflow-hidden", className)}
      {...handlers}
    >
      <div
        aria-hidden={!isRefreshing}
        className="pointer-events-none absolute inset-x-0 top-0 z-10 flex justify-center"
        style={{
          transform: `translateY(${Math.max(pullDistance - 28, isRefreshing ? 8 : -40)}px)`,
          opacity: indicatorVisible ? Math.max(progress, isRefreshing ? 1 : 0) : 0,
          transition: pullDistance === 0 && !isRefreshing ? "transform 200ms ease-out, opacity 150ms ease-out" : "none",
        }}
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-full border bg-background shadow-sm">
          <Loader2 className={cn("h-4 w-4 text-muted-foreground", isRefreshing && "animate-spin")} />
        </div>
      </div>
      {children}
    </div>
  );
}
