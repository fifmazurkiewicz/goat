import type { TemplateOverrides } from "@/types/api";

/** Column in the form editor (React Hook Form `useFieldArray`). */
export interface PersonaColumnDraft {
  name: string;
}

/**
 * UI ↔ API mapping for `template_overrides`.
 * Backend contract: `{ columns: string[] }` (`resolve_persona_columns`).
 * Legacy shapes (an array of `{name}` or an array of strings) are tolerated on read.
 */
export function columnsFromTemplateOverrides(
  overrides: TemplateOverrides | PersonaColumnDraft[] | string[] | null | undefined
): PersonaColumnDraft[] {
  if (!overrides) {
    return [{ name: "Kolumna 1" }];
  }

  if (Array.isArray(overrides)) {
    const mapped = overrides
      .map((item) => {
        if (typeof item === "string") return { name: item };
        if (item && typeof item === "object" && "name" in item) {
          return { name: String((item as PersonaColumnDraft).name ?? "") };
        }
        return null;
      })
      .filter((item): item is PersonaColumnDraft => item !== null);
    return mapped.length > 0 ? mapped : [{ name: "Kolumna 1" }];
  }

  if (Array.isArray(overrides.columns) && overrides.columns.length > 0) {
    return overrides.columns.map((name) => ({ name: String(name) }));
  }

  return [{ name: "Kolumna 1" }];
}

export function templateOverridesFromColumns(columns: PersonaColumnDraft[]): TemplateOverrides {
  return {
    columns: columns.map((column) => column.name.trim()).filter(Boolean),
  };
}
