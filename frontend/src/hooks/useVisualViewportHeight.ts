import { useEffect } from "react";

const CSS_VAR = "--app-height";

/**
 * Ustawia `--app-height` na wysokość visual viewport.
 * Na iOS/Android kurczy layout razem z klawiaturą i paskiem URL —
 * composer czatu zostaje nad klawiaturą zamiast pod nią.
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
