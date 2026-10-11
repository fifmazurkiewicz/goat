import { findExerciseColumnIndex } from "@/lib/exercise-matcher";
import type { ResultDetailCell } from "@/types/api";

/** Manual entry → `details` (ADR-25): filled columns in plan order + the exercise cell for `metric`. */
export function buildDetailsFromInputs(
  columns: string[],
  values: string[]
): { details: ResultDetailCell[] | null; exercise: string } {
  const cells = columns
    .map((label, index) => ({ label, value: (values[index] ?? "").trim() }))
    .filter((cell) => cell.value !== "");
  const exercise = (values[findExerciseColumnIndex(columns)] ?? "").trim();
  return { details: cells.length ? cells : null, exercise };
}
