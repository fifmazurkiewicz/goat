import type { Exercise } from "@/types/api";

/**
 * Matcher for clickable exercises in plans (ADR-14 amendment 2026-08-23): a plan table row
 * is free-form text from the LLM (e.g. "Barbell squat", "przysiad ze sztanga",
 * "Wyciskanie lezaco 3x8") — we match it against the catalog by normalized names
 * (PL, EN) and the slug.
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

/** Index: normalized key → exercise. Build once per list render (useMemo). */
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

    // Fallback: the cell contains the full normalized key of an exercise
    // (e.g. "przysiad ze sztanga 3x8" contains "przysiad ze sztanga").
    for (const [key, exercise] of index) {
      if (key.length >= 5 && normalizedCell.includes(key)) return exercise;
    }
    return null;
  };
}
