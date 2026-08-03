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
 * Placeholder — docelowo `personas` zasilane przez TanStack Query
 * (server state), ten store trzyma tylko wybór aktywnej persony (UI state)
 * i cache współdzielony z galerią onboardingu (docs/technical/frontend.md #1).
 * Guard "min. 1 aktywna persona" na /chat i /plans — odłożony (ADR-8).
 *
 * `hasActivePersona` jest przeliczane przy każdym `setPersonas` (nie jako
 * JS getter na stanie) — zustand kopiuje stan przez Object.assign przy
 * `set`, co "zamroziłoby" wartość gettera zamiast trzymać go reaktywnym.
 */
export const usePersonaStore = create<PersonaState>((set) => ({
  personas: [],
  activePersonaId: null,
  hasActivePersona: false,
  setPersonas: (personas) => set({ personas, hasActivePersona: personas.length > 0 }),
  setActivePersonaId: (id) => set({ activePersonaId: id }),
}));
