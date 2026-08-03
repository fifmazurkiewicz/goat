import "@testing-library/jest-dom/vitest";

// jsdom nie implementuje matchMedia — potrzebne dla `useMediaQuery`/`useIsMobile`
// (docs/technical/frontend.md sekcje 5 i 11, breakpointy mobile/desktop).
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}
