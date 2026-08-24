import { useMemo } from "react";
import { Link } from "react-router-dom";

import { useExercises } from "@/hooks/useExercises";
import { useIsMobile } from "@/hooks/useMediaQuery";
import { buildExerciseMatcher } from "@/lib/exercise-matcher";
import { normalizePlanRow } from "@/lib/plan-item-content";
import { cn } from "@/lib/utils";
import type { Exercise, PlanItemContent } from "@/types/api";

interface PlanItemTableProps {
  content: PlanItemContent;
  variant?: "table" | "cards";
}

function ExerciseCell({ cell, exercise }: { cell: string; exercise: Exercise }) {
  return (
    <Link
      to={`/exercises/${exercise.slug}`}
      className="font-medium text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
      title={`${exercise.name} — zobacz opis`}
    >
      {cell}
    </Link>
  );
}

/**
 * Generic {title, columns, rows, notes} renderer — `variant: 'table' | 'cards'`
 * (docs/technical/frontend.md section 11): mobile renders a card-per-row list
 * (column label + value, like a definition list) instead of horizontal scroll inside
 * `<table>`. Cells in the first column matched against the exercise catalog become
 * links to `/exercises/:slug` (ADR-14 update 2026-08-23).
 */
export function PlanItemTable({ content, variant }: PlanItemTableProps) {
  const isMobile = useIsMobile();
  const resolvedVariant = variant ?? (isMobile ? "cards" : "table");
  const { data: exercises } = useExercises();
  const matchExercise = useMemo(() => buildExerciseMatcher(exercises ?? []), [exercises]);

  if (content.rows.length === 0) {
    return <p className="text-sm text-muted-foreground">Brak pozycji do wyświetlenia.</p>;
  }

  const normalizedRows = content.rows.map((row) => normalizePlanRow(row, content.columns));
  const hasAnyValue = normalizedRows.some((row) => row.some((cell) => cell.trim() !== ""));

  if (!hasAnyValue) {
    return <p className="text-sm text-muted-foreground">Brak szczegółów w tabeli — zobacz notatkę poniżej.</p>;
  }

  const matchedRows = normalizedRows.map((row) => ({
    cells: row,
    exercise: matchExercise(row[0] ?? ""),
  }));

  if (resolvedVariant === "cards") {
    return (
      <div className="space-y-2">
        {matchedRows.map(({ cells, exercise }, rowIndex) => (
          <div key={rowIndex} className="rounded-md border p-3">
            {content.columns.map((column, colIndex) => (
              <div
                key={column}
                className={cn(
                  "flex justify-between gap-3 py-0.5 text-sm",
                  colIndex === 0 && "font-medium"
                )}
              >
                <span className="text-muted-foreground">{column}</span>
                <span className="text-right">
                  {cells[colIndex]?.trim() ? (
                    colIndex === 0 && exercise ? (
                      <ExerciseCell cell={cells[colIndex]} exercise={exercise} />
                    ) : (
                      cells[colIndex]
                    )
                  ) : (
                    "—"
                  )}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            {content.columns.map((column) => (
              <th key={column} className="whitespace-nowrap px-2 py-1.5 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matchedRows.map(({ cells, exercise }, rowIndex) => (
            <tr key={rowIndex} className="border-b last:border-0">
              {content.columns.map((column, colIndex) => (
                <td key={column} className="px-2 py-1.5">
                  {cells[colIndex]?.trim() ? (
                    colIndex === 0 && exercise ? (
                      <ExerciseCell cell={cells[colIndex]} exercise={exercise} />
                    ) : (
                      cells[colIndex]
                    )
                  ) : (
                    "—"
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
