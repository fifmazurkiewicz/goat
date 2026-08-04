import { useIsMobile } from "@/hooks/useMediaQuery";
import { cn } from "@/lib/utils";
import { normalizePlanRow } from "@/lib/plan-item-content";
import type { PlanItemContent } from "@/types/api";

interface PlanItemTableProps {
  content: PlanItemContent;
  variant?: "table" | "cards";
}

/**
 * Generyczny renderer {title, columns, rows, notes} — `variant: 'table' | 'cards'`
 * (docs/technical/frontend.md sekcja 11): mobile renderuje listę card-per-row (etykieta
 * kolumny + wartość, jak definition list) zamiast poziomego scrolla w `<table>`.
 */
export function PlanItemTable({ content, variant }: PlanItemTableProps) {
  const isMobile = useIsMobile();
  const resolvedVariant = variant ?? (isMobile ? "cards" : "table");

  if (content.rows.length === 0) {
    return <p className="text-sm text-muted-foreground">Brak pozycji do wyświetlenia.</p>;
  }

  const normalizedRows = content.rows.map((row) => normalizePlanRow(row, content.columns));
  const hasAnyValue = normalizedRows.some((row) => row.some((cell) => cell.trim() !== ""));

  if (!hasAnyValue) {
    return <p className="text-sm text-muted-foreground">Brak szczegółów w tabeli — zobacz notatkę poniżej.</p>;
  }

  if (resolvedVariant === "cards") {
    return (
      <div className="space-y-2">
        {normalizedRows.map((row, rowIndex) => (
          <div key={rowIndex} className="rounded-md border p-3">
            {content.columns.map((column, colIndex) => (
              <div key={column} className={cn("flex justify-between gap-3 py-0.5 text-sm", colIndex === 0 && "font-medium")}>
                <span className="text-muted-foreground">{column}</span>
                <span className="text-right">{row[colIndex]?.trim() ? row[colIndex] : "—"}</span>
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
          {normalizedRows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-b last:border-0">
              {content.columns.map((column, colIndex) => (
                <td key={column} className="px-2 py-1.5">
                  {row[colIndex]?.trim() ? row[colIndex] : "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
