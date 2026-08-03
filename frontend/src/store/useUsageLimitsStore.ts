import { create } from "zustand";
import type { UsageLimits } from "@/types/api";

interface UsageLimitsState {
  limits: UsageLimits | null;
  isNearLimit: boolean;
  setLimits: (limits: UsageLimits) => void;
}

/**
 * Placeholder — docelowo odświeżany po 429 lub po nagłówkach usage w
 * odpowiedzi API (docs/technical/frontend.md sekcja 2), zasila proaktywny
 * badge "90% limitu" (sekcja 10).
 *
 * TODO: `isNearLimit` wymaga znajomości limitu (nie tylko `used`) —
 * backend jeszcze nie eksponuje `messages_limit`/`tokens_limit` per tier.
 * Na razie zawsze `false`; podłączyć realne porównanie `used / limit >= 0.9`
 * gdy kontrakt `/usage` z backendu będzie znany.
 */
export const useUsageLimitsStore = create<UsageLimitsState>((set) => ({
  limits: null,
  isNearLimit: false,
  setLimits: (limits) => set({ limits }),
}));
