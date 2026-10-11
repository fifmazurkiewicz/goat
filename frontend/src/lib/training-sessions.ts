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

function formatValue(value: number): string {
  return String(value).replace(".", ",");
}

/** Row cells for one result — `details` as logged, else a legacy fallback (metric + value). */
function resultCells(result: Result): ResultDetailCell[] {
  const cells = result.details?.length
    ? [...result.details]
    : [
        { label: EXERCISE_LABEL, value: result.metric },
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
