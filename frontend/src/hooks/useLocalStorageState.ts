import { useCallback, useState } from "react";

/**
 * Generyczny `useState` persystowany w localStorage — używany np. dla stanu
 * open/closed `PersonaSessionDrawer` (docs/technical/frontend.md sekcja 4).
 */
export function useLocalStorageState<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored !== null ? (JSON.parse(stored) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const setPersistedValue = useCallback(
    (next: T | ((prev: T) => T)) => {
      setValue((prev) => {
        const resolved = typeof next === "function" ? (next as (prev: T) => T)(prev) : next;
        try {
          localStorage.setItem(key, JSON.stringify(resolved));
        } catch {
          // localStorage niedostępny — brak persystencji, nie krytyczne.
        }
        return resolved;
      });
    },
    [key]
  );

  return [value, setPersistedValue] as const;
}
