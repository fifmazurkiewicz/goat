import { useCallback, useEffect, useRef, useState } from "react";

export const PULL_THRESHOLD_PX = 72;

export interface UsePullToRefreshOptions {
  onRefresh: () => Promise<unknown> | void;
  threshold?: number;
  /** Locks the gesture (e.g. chat stream in progress) — pulls are then ignored. */
  isLocked?: boolean;
}

export interface PullToRefreshState {
  pullDistance: number;
  isRefreshing: boolean;
}

/**
 * Pull-to-refresh (mobile, touch-only) — spec 2026-08-22-pull-to-refresh-design.md.
 * Pointer events (`pointerType === "touch"`); "is the scroller under the finger at the top"
 * is decided ONCE on pointerdown (perf — pointermove arrives every ~8 ms). On iOS
 * scroll takes over the gesture via pointercancel, so the wrapper also attaches touchmove
 * with a conditional preventDefault ({passive: false}) — only during an active pull.
 */
export function usePullToRefresh({ onRefresh, threshold = PULL_THRESHOLD_PX, isLocked = false }: UsePullToRefreshOptions) {
  const [state, setState] = useState<PullToRefreshState>({ pullDistance: 0, isRefreshing: false });
  const startRef = useRef<{ x: number; y: number; canPull: boolean } | null>(null);
  const refreshingRef = useRef(false);
  const stateRef = useRef(state);
  stateRef.current = state;
  const containerRef = useRef<HTMLDivElement | null>(null);

  // iOS Safari: without preventDefault on touchmove, scroll wins and sends pointercancel,
  // before the pull reaches the threshold. Active only while we hold an active pull (pullDistance > 0).
  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const onTouchMove = (event: TouchEvent) => {
      if (!startRef.current || !startRef.current.canPull) return;
      if (refreshingRef.current || stateRef.current.pullDistance > 0) {
        if (event.cancelable) event.preventDefault();
      }
    };
    node.addEventListener("touchmove", onTouchMove, { passive: false });
    return () => node.removeEventListener("touchmove", onTouchMove);
  }, []);

  const setPull = useCallback((pullDistance: number) => {
    setState((prev) =>
      prev.pullDistance === pullDistance ? prev : { ...prev, pullDistance }
    );
  }, []);

  const onPointerStart = useCallback(
    (e: React.PointerEvent) => {
      if (e.pointerType !== "touch") return;
      startRef.current = {
        x: e.clientX,
        y: e.clientY,
        canPull:
          !refreshingRef.current &&
          !isLocked &&
          canPullFromTarget(e.target as Element | null),
      };
      if (!startRef.current.canPull) setPull(0);
    },
    [isLocked, setPull]
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      const start = startRef.current;
      if (!start || refreshingRef.current) return;
      if (!start.canPull) return;
      const dy = e.clientY - start.y;
      const dx = Math.abs(e.clientX - start.x);
      // Horizontal swipe or upward movement → gesture canceled until next touch (GWT-2/6).
      if (dy <= 0 || dx > dy) {
        start.canPull = false;
        setPull(0);
        return;
      }
      const damped = dy <= threshold ? dy : threshold + (dy - threshold) * 0.3;
      setPull(Math.round(damped));
    },
    [setPull, threshold]
  );

  const onPointerEnd = useCallback(() => {
    const start = startRef.current;
    startRef.current = null;
    if (!start || refreshingRef.current || !start.canPull) return;
    const current = stateRef.current.pullDistance;
    if (current >= threshold) {
      setState({ pullDistance: threshold, isRefreshing: true });
      refreshingRef.current = true;
      void Promise.resolve(onRefresh()).finally(() => {
        refreshingRef.current = false;
        setState({ pullDistance: 0, isRefreshing: false });
      });
    } else {
      setPull(0);
    }
  }, [onRefresh, setPull, threshold]);

  return {
    ...state,
    containerRef,
    handlers: { onPointerDown: onPointerStart, onPointerMove, onPointerUp: onPointerEnd, onPointerCancel: onPointerEnd },
  };
}

/** Whether no scroller between the target and the PTR container is scrolled down. */
function canPullFromTarget(target: Element | null): boolean {
  let node: Element | null = target;
  while (node) {
    if (node instanceof HTMLElement && node.scrollHeight > node.clientHeight) {
      const overflowY = getComputedStyle(node).overflowY;
      if ((overflowY === "auto" || overflowY === "scroll") && node.scrollTop > 0) {
        return false;
      }
    }
    // The PTR container ends the chain — above it the gesture makes no sense anyway.
    if (node instanceof HTMLElement && node.dataset.pullToRefresh !== undefined) break;
    node = node.parentElement;
  }
  return true;
}
