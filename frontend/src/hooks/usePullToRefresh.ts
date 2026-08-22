import { useCallback, useEffect, useRef, useState } from "react";

export const PULL_THRESHOLD_PX = 72;

export interface UsePullToRefreshOptions {
  onRefresh: () => Promise<unknown> | void;
  threshold?: number;
  /** Blokada gestu (np. stream czatu w toku) — pociągnięcia są wtedy ignorowane. */
  isLocked?: boolean;
}

export interface PullToRefreshState {
  pullDistance: number;
  isRefreshing: boolean;
}

/**
 * Pull-to-refresh (mobile, touch-only) — spec 2026-08-22-pull-to-refresh-design.md.
 * Pointer events (`pointerType === "touch"`); „czy scroller pod palcem jest na górze"
 * rozstrzygane RAZ na pointerdown (perf — pointermove przychodzi co ~8 ms). Na iOS
 * scroll przejmuje gest przez pointercancel, więc wrapper dołącza też touchmove
 * z warunkowym preventDefault ({passive: false}) — tylko w trakcie aktywnego pulla.
 */
export function usePullToRefresh({ onRefresh, threshold = PULL_THRESHOLD_PX, isLocked = false }: UsePullToRefreshOptions) {
  const [state, setState] = useState<PullToRefreshState>({ pullDistance: 0, isRefreshing: false });
  const startRef = useRef<{ x: number; y: number; canPull: boolean } | null>(null);
  const refreshingRef = useRef(false);
  const stateRef = useRef(state);
  stateRef.current = state;
  const containerRef = useRef<HTMLDivElement | null>(null);

  // iOS Safari: bez preventDefault na touchmove scroll wygra i wyśle pointercancel,
  // zanim pull osiągnie próg. Aktywne tylko gdy trzymamy aktywny pull (pullDistance > 0).
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
      // Poziomy swipe albo ruch w górę → gest anulowany do następnego dotyku (GWT-2/6).
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

/** Czy żaden scroller między targetem a kontenerem PTR nie jest przewinięty w dół. */
function canPullFromTarget(target: Element | null): boolean {
  let node: Element | null = target;
  while (node) {
    if (node instanceof HTMLElement && node.scrollHeight > node.clientHeight) {
      const overflowY = getComputedStyle(node).overflowY;
      if ((overflowY === "auto" || overflowY === "scroll") && node.scrollTop > 0) {
        return false;
      }
    }
    // Kontener PTR kończy łańcuch — powyżej niego gest i tak nie ma sensu.
    if (node instanceof HTMLElement && node.dataset.pullToRefresh !== undefined) break;
    node = node.parentElement;
  }
  return true;
}
