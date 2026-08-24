import { create } from "zustand";
import type { Persona } from "@/types/api";

interface PersonaState {
  personas: Persona[];
  activePersonaId: string | null;
  hasActivePersona: boolean;
  setPersonas: (personas: Persona[]) => void;
  setActivePersonaId: (id: string | null) => void;
}

/**
 * Placeholder — eventually `personas` will be fed by TanStack Query
 * (server state), this store only holds the active persona selection (UI state)
 * and a cache shared with the onboarding gallery (docs/technical/frontend.md #1).
 * "Min. 1 active persona" guard on /chat and /plans — deferred (ADR-8).
 *
 * `hasActivePersona` is recomputed on every `setPersonas` (not as a
 * JS getter on the state) — zustand copies state via Object.assign on
 * `set`, which would "freeze" the getter's value instead of keeping it reactive.
 */
export const usePersonaStore = create<PersonaState>((set) => ({
  personas: [],
  activePersonaId: null,
  hasActivePersona: false,
  setPersonas: (personas) => set({ personas, hasActivePersona: personas.length > 0 }),
  setActivePersonaId: (id) => set({ activePersonaId: id }),
}));
