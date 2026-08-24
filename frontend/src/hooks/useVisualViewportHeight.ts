import { useEffect } from "react";

const CSS_VAR = "--app-height";

/**
 * Sets `--app-height` to the visual viewport height.
 * On iOS/Android this shrinks the layout together with the keyboard and URL bar —
 * the chat composer stays above the keyboard instead of below it.
 */
export function useVisualViewportHeight(): void {
  useEffect(() => {
    const root = document.documentElement;

    function apply() {
      const height = window.visualViewport?.height ?? window.innerHeight;
      root.style.setProperty(CSS_VAR, `${Math.round(height)}px`);
    }

    apply();
    window.visualViewport?.addEventListener("resize", apply);
    window.visualViewport?.addEventListener("scroll", apply);
    window.addEventListener("orientationchange", apply);
    return () => {
      window.visualViewport?.removeEventListener("resize", apply);
      window.visualViewport?.removeEventListener("scroll", apply);
      window.removeEventListener("orientationchange", apply);
      root.style.removeProperty(CSS_VAR);
    };
  }, []);
}
