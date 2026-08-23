import type { Exercise } from "@/types/api";

/**
 * Matcher klikalnych ćwiczeń w planach (ADR-14 nowelizacja 2026-08-23): wiersz tabeli
 * planu to wolny tekst od LLM (np. "Przysiad ze sztangą", "barbell squat", "Wyciskanie
 * leżąc 3×8") — dopasowujemy go do katalogu po znormalizowanych nazwach (PL, EN) i slugu.
 */

const STOP_WORDS = new Set(["cwiczenie", "exercise"]);

export function normalizeExerciseText(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ł/g, "l")
    .replace(/[^a-z0-9 ]+/g, " ")
    .split(/\s+/)
    .filter((word) => word && !STOP_WORDS.has(word))
    .sort()
    .join(" ")
    .trim();
}

function exerciseKeys(exercise: Exercise): string[] {
  return [exercise.name, exercise.name_en, exercise.slug.replace(/-/g, " ")]
    .filter((value): value is string => Boolean(value))
    .map(normalizeExerciseText)
    .filter(Boolean);
}

/** Indeks: znormalizowany klucz → exercise. Buduj raz per render listy (useMemo). */
export function buildExerciseMatcher(exercises: Exercise[]): (cell: string) => Exercise | null {
  const index = new Map<string, Exercise>();
  for (const exercise of exercises) {
    for (const key of exerciseKeys(exercise)) {
      if (!index.has(key)) index.set(key, exercise);
    }
  }

  return (cell: string): Exercise | null => {
    const normalizedCell = normalizeExerciseText(cell);
    if (!normalizedCell) return null;
    const direct = index.get(normalizedCell);
    if (direct) return direct;

    // Fallback: komórka zawiera pełny znormalizowany klucz ćwiczenia
    // (np. "przysiad ze sztanga 3x8" zawiera "przysiad ze sztanga").
    for (const [key, exercise] of index) {
      if (key.length >= 5 && normalizedCell.includes(key)) return exercise;
    }
    return null;
  };
}
