import type { Persona, PersonaType, ResultCategory } from "@/types/api";

/** Mapowanie typ persony → kategoria wyników (allowed_metrics / GET /results). */
const PERSONA_TYPE_TO_CATEGORY: Partial<Record<PersonaType, ResultCategory>> = {
  personal_trainer: "strength",
  motor_coach: "strength",
  dietitian: "diet",
  badminton_coach: "badminton",
  // sport_psychologist / psychologist — bez osobnej kategorii wyników w MVP
};

const CATEGORY_LABELS: Record<ResultCategory, string> = {
  // strength obejmuje siłownię + bieganie/kondycję (motor_coach) — nie tylko „Siłownia”.
  strength: "Trening",
  diet: "Dieta",
  swimming: "Basen",
  triathlon: "Triathlon",
  badminton: "Badminton",
  custom: "Inne",
};

const KNOWN_CATEGORIES = new Set<string>(Object.keys(CATEGORY_LABELS));

const CATEGORY_ORDER: ResultCategory[] = [
  "strength",
  "diet",
  "swimming",
  "triathlon",
  "badminton",
  "custom",
];

export interface ResultCategoryTab {
  key: ResultCategory;
  label: string;
}

export function categoryLabel(key: ResultCategory): string {
  return CATEGORY_LABELS[key] ?? key;
}

/**
 * Taby `/results`: persony usera + kategorie, w których już są wpisy
 * (np. model zapisał bieg jako `triathlon` / `custom` — bez tego zakładka znika).
 */
export function resultCategoryTabsFromPersonas(
  personas: Persona[],
  options?: { categoriesWithData?: Iterable<string> }
): ResultCategoryTab[] {
  const source = personas.some((p) => p.active) ? personas.filter((p) => p.active) : personas;
  const byKey = new Map<ResultCategory, string>();

  for (const persona of source) {
    if (persona.type === "custom") {
      const raw = persona.custom_result_category?.trim();
      if (!raw) continue;
      if (KNOWN_CATEGORIES.has(raw) && raw !== "custom") {
        const key = raw as ResultCategory;
        byKey.set(key, CATEGORY_LABELS[key]);
      } else {
        byKey.set("custom", raw);
      }
      continue;
    }

    const key = PERSONA_TYPE_TO_CATEGORY[persona.type];
    if (key) {
      byKey.set(key, CATEGORY_LABELS[key]);
    }
  }

  for (const raw of options?.categoriesWithData ?? []) {
    if (!KNOWN_CATEGORIES.has(raw)) continue;
    const key = raw as ResultCategory;
    if (!byKey.has(key)) {
      byKey.set(key, CATEGORY_LABELS[key]);
    }
  }

  return CATEGORY_ORDER.filter((key) => byKey.has(key)).map((key) => ({
    key,
    label: byKey.get(key)!,
  }));
}
