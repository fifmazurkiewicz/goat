import type { Exercise } from "@/types/api";

/**
 * Matcher for clickable exercises in plans (ADR-14 amendment 2026-08-23): a plan table row
 * is free-form text from the LLM (e.g. "Barbell squat", "przysiad ze sztanga",
 * "Wyciskanie lezaco 3x8") — we match it against the catalog by normalized names
 * (PL, EN) and the slug.
 *
 * Column detection: motor_coach plans often put Day first and Ćwiczenie second —
 * use `findExerciseColumnIndex`, not a hard-coded 0.
 */

const STOP_WORDS = new Set(["cwiczenie", "exercise"]);
const EXERCISE_HEADER_WORDS = new Set(["cwiczenie", "exercise"]);

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

function normalizeHeader(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ł/g, "l")
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Index of the exercise-name column. Prefers a header containing Ćwiczenie/Exercise;
 * falls back to 0 (legacy layouts where the name is first).
 */
export function findExerciseColumnIndex(columns: string[]): number {
  const idx = columns.findIndex((col) =>
    normalizeHeader(col)
      .split(" ")
      .some((word) => EXERCISE_HEADER_WORDS.has(word))
  );
  return idx >= 0 ? idx : 0;
}

function exerciseKeys(exercise: Exercise): string[] {
  return [exercise.name, exercise.name_en, exercise.slug.replace(/-/g, " ")]
    .filter((value): value is string => Boolean(value))
    .map(normalizeExerciseText)
    .filter(Boolean);
}

/** LLM cells often list alternatives (`LUB` / `lub` / `or`) or slash variants. */
export function exerciseCellCandidates(cell: string): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  const push = (raw: string) => {
    const trimmed = raw.replace(/\s+/g, " ").trim();
    if (!trimmed || seen.has(trimmed)) return;
    seen.add(trimmed);
    out.push(trimmed);
  };

  push(cell);
  for (const alt of cell.split(/\s+(?:lub|or)\s+/i)) {
    push(alt);
    push(alt.replace(/\([^)]*\)/g, " "));
    for (const slashPart of alt.split(/\s*\/\s*/)) {
      push(slashPart);
      push(slashPart.replace(/\([^)]*\)/g, " "));
    }
  }
  return out;
}

/** Index: normalized key → exercise. Build once per list render (useMemo). */
export function buildExerciseMatcher(exercises: Exercise[]): (cell: string) => Exercise | null {
  const index = new Map<string, Exercise>();
  for (const exercise of exercises) {
    for (const key of exerciseKeys(exercise)) {
      if (!index.has(key)) index.set(key, exercise);
    }
  }

  const matchOne = (candidate: string): Exercise | null => {
    const normalizedCell = normalizeExerciseText(candidate);
    if (!normalizedCell) return null;
    const direct = index.get(normalizedCell);
    if (direct) return direct;

    // Fallback: the cell contains the full normalized key of an exercise
    // (e.g. "przysiad ze sztanga 3x8" contains "przysiad ze sztanga").
    // Also: bag-of-words — "Calf raise 2-leg …" still contains {calf, raise}.
    const cellWords = new Set(normalizedCell.split(" ").filter(Boolean));
    for (const [key, exercise] of index) {
      if (key.length < 5) continue;
      if (normalizedCell.includes(key)) return exercise;
      const keyWords = key.split(" ").filter(Boolean);
      if (keyWords.length >= 2 && keyWords.every((w) => cellWords.has(w))) return exercise;
    }
    return null;
  };

  return (cell: string): Exercise | null => {
    for (const candidate of exerciseCellCandidates(cell)) {
      const hit = matchOne(candidate);
      if (hit) return hit;
    }
    return null;
  };
}
