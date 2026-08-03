import type { Persona } from "@/types/api";

/**
 * Filtruje aktywne persony po `slug`/nazwie dla dropdownu "/" w sesji `general`
 * (ADR-13) — surowa składnia `/slug` bez podpowiedzi jest praktycznie nieodkrywalna.
 */
export function filterPersonasBySlug(personas: Persona[], query: string): Persona[] {
  const activePersonas = personas.filter((p) => p.active);
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return activePersonas;
  return activePersonas.filter(
    (p) => p.slug.toLowerCase().startsWith(normalizedQuery) || p.name.toLowerCase().includes(normalizedQuery)
  );
}
