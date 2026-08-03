import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { useUsageLimitsStore } from "@/store/useUsageLimitsStore";
import type { UsageLimits } from "@/types/api";

export const USAGE_QUERY_KEY = ["usage"] as const;

/**
 * Budżet USD per konto (`profiles.usage_budget_usd`, ADR-16) + zużycie bieżącego okresu.
 * Zasila `useUsageLimitsStore` (badge "90% budżetu"). Odświeżany też po 429
 * (`useChatStream` wywołuje `queryClient.invalidateQueries(USAGE_QUERY_KEY)`).
 */
export function useUsage() {
  const setLimits = useUsageLimitsStore((state) => state.setLimits);

  return useQuery({
    queryKey: USAGE_QUERY_KEY,
    queryFn: async () => {
      const data = await apiFetch<UsageLimits>("/api/v1/usage");
      setLimits(data);
      return data;
    },
    staleTime: 30_000,
  });
}

export function useRefreshUsage() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: USAGE_QUERY_KEY });
}
