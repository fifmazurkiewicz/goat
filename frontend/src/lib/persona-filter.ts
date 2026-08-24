import type { Persona } from "@/types/api";

/**
 * Filters active personas by `slug`/name for the "/" dropdown in the `general`
 * session (ADR-13) — the raw `/slug` syntax without hints is practically undiscoverable.
 */
export function filterPersonasBySlug(personas: Persona[], query: string): Persona[] {
  const activePersonas = personas.filter((p) => p.active);
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return activePersonas;
  return activePersonas.filter(
    (p) => p.slug.toLowerCase().startsWith(normalizedQuery) || p.name.toLowerCase().includes(normalizedQuery)
  );
}
