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
  strength: "Siłownia",
  diet: "Dieta",
  swimming: "Basen",
  triathlon: "Triathlon",
  badminton: "Badminton",
  custom: "Inne",
};

const KNOWN_CATEGORIES = new Set<string>(Object.keys(CATEGORY_LABELS));

export interface ResultCategoryTab {
  key: ResultCategory;
  label: string;
}

/**
 * Taby `/results` z person usera — nie hardkodowana lista „wszystkich sportów”.
 * Preferuje persony `active`; gdy brak aktywnych, bierze wszystkie własne.
 */
export function resultCategoryTabsFromPersonas(personas: Persona[]): ResultCategoryTab[] {
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

  const order: ResultCategory[] = [
    "strength",
    "diet",
    "swimming",
    "triathlon",
    "badminton",
    "custom",
  ];
  return order.filter((key) => byKey.has(key)).map((key) => ({ key, label: byKey.get(key)! }));
}
