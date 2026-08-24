import { useCallback, useState } from "react";

/**
 * Generic `useState` persisted in localStorage — used e.g. for the open/closed
 * state of `PersonaSessionDrawer` (docs/technical/frontend.md section 4).
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
          // localStorage unavailable — no persistence, not critical.
        }
        return resolved;
      });
    },
    [key]
  );

  return [value, setPersistedValue] as const;
}
