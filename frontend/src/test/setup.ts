import "@testing-library/jest-dom/vitest";

// jsdom does not implement matchMedia — needed for `useMediaQuery`/`useIsMobile`
// (docs/technical/frontend.md sections 5 and 11, mobile/desktop breakpoints).
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
