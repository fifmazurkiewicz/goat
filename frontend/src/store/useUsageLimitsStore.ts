import { create } from "zustand";
import type { UsageLimits } from "@/types/api";

interface UsageLimitsState {
  limits: UsageLimits | null;
  isNearLimit: boolean;
  setLimits: (limits: UsageLimits) => void;
}

const NEAR_LIMIT_RATIO = 0.9;

/**
 * Refreshed after a 429 (via `useUsage` refetch) or after a successful `GET /api/v1/usage`
 * (docs/technical/frontend.md section 2), powers the proactive "90% of budget" badge
 * (section 10 — budget in USD, ADR-16, not a Free/Pro plan).
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
