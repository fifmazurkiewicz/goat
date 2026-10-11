import { personaResultCategory } from "@/lib/result-categories";
import type { Persona, PlanItemContent, Result, ResultCategory, ResultDetailCell } from "@/types/api";

const EXERCISE_LABEL = "Ćwiczenie";
const RESULT_LABEL = "Wynik";
const NOTES_LABEL = "Uwagi";

export interface TrainingSession {
  date: string;
  results: Result[];
  personaIds: (string | null)[];
  content: PlanItemContent;
}

// Trailing unit tokens of snake_case metric keys — the unit is already shown in "Wynik".
const UNIT_SUFFIXES = [["min", "per", "km"], ["kg"], ["min"], ["km"], ["m"], ["s"], ["g"], ["kcal"]];

/**
 * Display name for a legacy metric key: `hip_thrust_weight_kg` → "Hip thrust",
 * `bench_press_1rm` → "Bench press 1RM". Free-text metrics (no underscore) stay as logged.
 */
export function humanizeMetric(metric: string): string {
  if (!metric.includes("_")) return metric;
  let tokens = metric.toLowerCase().split("_").filter(Boolean);
  const suffix = UNIT_SUFFIXES.find(
    (unit) => tokens.length > unit.length && unit.every((token, i) => tokens[tokens.length - unit.length + i] === token)
  );
  if (suffix) tokens = tokens.slice(0, tokens.length - suffix.length);
  if (tokens.length > 1 && tokens[tokens.length - 1] === "weight") tokens = tokens.slice(0, -1);
  const text = tokens.map((token) => (token === "1rm" ? "1RM" : token)).join(" ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatValue(value: number): string {
  return String(value).replace(".", ",");
}

/** Row cells for one result — `details` as logged, else a legacy fallback (metric + value). */
function resultCells(result: Result): ResultDetailCell[] {
  const cells = result.details?.length
    ? [...result.details]
    : [
        { label: EXERCISE_LABEL, value: humanizeMetric(result.metric) },
        { label: RESULT_LABEL, value: `${formatValue(result.value)} ${result.unit ?? ""}`.trim() },
      ];
  if (result.notes && !cells.some((cell) => cell.label === NOTES_LABEL)) {
    cells.push({ label: NOTES_LABEL, value: result.notes });
  }
  return cells;
}

/** One day = one session (ADR-25): newest day first, entries in logging order. */
export function buildTrainingSessions(results: Result[]): TrainingSession[] {
  const byDate = new Map<string, Result[]>();
  for (const result of results) {
    byDate.set(result.logged_date, [...(byDate.get(result.logged_date) ?? []), result]);
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([date, dayResults]) => {
      const ordered = [...dayResults].sort((a, b) => a.created_at.localeCompare(b.created_at));
      const rowsCells = ordered.map(resultCells);
      const columns: string[] = [];
      for (const cells of rowsCells) {
        for (const cell of cells) if (!columns.includes(cell.label)) columns.push(cell.label);
      }
      // Notes last, whatever order the rows introduced it in.
      if (columns.includes(NOTES_LABEL)) columns.push(...columns.splice(columns.indexOf(NOTES_LABEL), 1));
      const rows = rowsCells.map((cells) =>
        columns.map((label) => cells.find((cell) => cell.label === label)?.value ?? "")
      );
      return {
        date,
        results: ordered,
        personaIds: [...new Set(ordered.map((r) => r.source_persona_id))],
        content: { title: date, columns, rows, notes: null },
      };
    });
}

/** Active personas logging into `category` that have plan columns — the session view applies. */
export function sessionPersonasForCategory(personas: Persona[], category: ResultCategory): Persona[] {
  return personas.filter(
    (persona) =>
      persona.active && personaResultCategory(persona) === category && (persona.plan_columns?.length ?? 0) > 0
  );
}
