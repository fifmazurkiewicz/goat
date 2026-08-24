import type { Exercise } from "@/types/api";

export const IDLE_SAMPLE_SIZE = 3;

export function pickRandomExercises(
  exercises: readonly Exercise[],
  count: number,
  random: () => number = Math.random,
): Exercise[] {
  if (exercises.length <= count) return [...exercises];
  const pool = [...exercises];
  for (let i = pool.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    const current = pool[i]!;
    pool[i] = pool[j]!;
    pool[j] = current;
  }
  return pool.slice(0, count);
}

function matchesQuery(exercise: Exercise, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;
  return (
    exercise.name.toLowerCase().includes(normalizedQuery) ||
    (exercise.name_en?.toLowerCase().includes(normalizedQuery) ?? false) ||
    exercise.categories.some((category) => category.toLowerCase().includes(normalizedQuery))
  );
}

function matchesCategory(exercise: Exercise, category: string): boolean {
  return category === "all" || exercise.categories.includes(category);
}

export function visibleExercises({
  all,
  sample,
  query,
  category,
}: {
  all: readonly Exercise[];
  sample: readonly Exercise[];
  query: string;
  category: string;
}): Exercise[] {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return [...sample];
  }
  return all.filter(
    (exercise) => matchesCategory(exercise, category) && matchesQuery(exercise, normalizedQuery),
  );
}
