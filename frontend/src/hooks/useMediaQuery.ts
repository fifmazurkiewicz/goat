import { useSyncExternalStore } from "react";

/**
 * `matchMedia`-owy breakpoint hook — używany wszędzie tam, gdzie layout przełącza się
 * między mobile/desktop wariantem (CalendarViewSwitcher, PlanItemTable `variant`,
 * Dialog/Sheet dla formularzy, docs/technical/frontend.md sekcje 5 i 11).
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

export const MOBILE_BREAKPOINT_QUERY = "(max-width: 767px)";

export function useIsMobile(): boolean {
  return useMediaQuery(MOBILE_BREAKPOINT_QUERY);
}
