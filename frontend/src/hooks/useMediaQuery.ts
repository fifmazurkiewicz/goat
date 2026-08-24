import { useSyncExternalStore } from "react";

/**
 * `matchMedia`-based breakpoint hook — used wherever the layout switches between
 * mobile and desktop variants (CalendarViewSwitcher, PlanItemTable `variant`,
 * Dialog/Sheet for forms, docs/technical/frontend.md sections 5 and 11).
 * Phone landscape (low height, wide width) is also treated as "mobile".
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onStoreChange) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onStoreChange);
      return () => mql.removeEventListener("change", onStoreChange);
    },
    () => window.matchMedia(query).matches,
    () => false
  );
}

export const MOBILE_BREAKPOINT_QUERY = "(max-width: 767px), (max-height: 500px)";

export function useIsMobile(): boolean {
  return useMediaQuery(MOBILE_BREAKPOINT_QUERY);
}
