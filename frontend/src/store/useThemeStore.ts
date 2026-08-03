import { create } from "zustand";

export type Theme = "light" | "dark";

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const STORAGE_KEY = "coach.theme";

function readPersistedTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // localStorage niedostępny — fallback do preferencji systemowej.
  }
  if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

function applyThemeClass(theme: Theme) {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", theme === "dark");
}

function persistTheme(theme: Theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // tryb prywatny itp. — brak persystencji, nie krytyczne.
  }
}

/**
 * Motyw jasny/ciemny — WYŁĄCZNIE localStorage, bez zapisu w bazie (ADR-15).
 * Przy skali kilku znanych userów i typowo jednym urządzeniu synchronizacja
 * między urządzeniami nie uzasadnia round-tripu do API.
 */
export const useThemeStore = create<ThemeState>((set, get) => {
  const initial = readPersistedTheme();
  applyThemeClass(initial);

  return {
    theme: initial,
    setTheme: (theme) => {
      persistTheme(theme);
      applyThemeClass(theme);
      set({ theme });
    },
    toggleTheme: () => {
      const next: Theme = get().theme === "dark" ? "light" : "dark";
      get().setTheme(next);
    },
  };
});
