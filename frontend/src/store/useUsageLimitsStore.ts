import { create } from "zustand";
import type { UsageLimits } from "@/types/api";

interface UsageLimitsState {
  limits: UsageLimits | null;
  isNearLimit: boolean;
  setLimits: (limits: UsageLimits) => void;
}

const NEAR_LIMIT_RATIO = 0.9;

/**
 * Odświeżany po 429 (przez refetch `useUsage`) lub po pomyślnym `GET /api/v1/usage`
 * (docs/technical/frontend.md sekcja 2), zasila proaktywny badge "90% budżetu"
 * (sekcja 10 — budżet w USD, ADR-16, nie plan Free/Pro).
 */
export const useUsageLimitsStore = create<UsageLimitsState>((set) => ({
  limits: null,
  isNearLimit: false,
  setLimits: (limits) =>
    set({
      limits,
      isNearLimit:
        limits.usage_budget_usd > 0 && limits.cost_usd_used / limits.usage_budget_usd >= NEAR_LIMIT_RATIO,
    }),
}));
