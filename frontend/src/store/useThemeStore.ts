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
    // localStorage unavailable — fallback to system preference.
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
    // private mode etc. — no persistence, not critical.
  }
}

/**
 * Light/dark theme — localStorage ONLY, with no DB persistence (ADR-15).
 * At the scale of a few known users and typically one device, cross-device
 * sync does not justify an API round-trip.
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
