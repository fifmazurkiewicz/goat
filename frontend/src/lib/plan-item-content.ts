/** Normalization of `plan_items.content.rows` — the backend stores rows as objects
 *  `{ [column]: value }`, while the frontend historically expected positional arrays. */
export type PlanItemRow = (string | number)[] | Record<string, string | number>;

export function normalizePlanRow(row: PlanItemRow, columns: string[]): string[] {
  if (Array.isArray(row)) {
    return columns.map((_, index) => {
      const value = row[index];
      return value === undefined || value === null || value === "" ? "" : String(value);
    });
  }
  if (row && typeof row === "object") {
    return columns.map((column) => {
      const value = row[column];
      return value === undefined || value === null || value === "" ? "" : String(value);
    });
  }
  return columns.map(() => "");
}

export function formatPlanRowForChat(row: PlanItemRow, columns: string[]): string {
  return normalizePlanRow(row, columns)
    .map((value, index) => `${columns[index]}: ${value || "—"}`)
    .join(" | ");
}
