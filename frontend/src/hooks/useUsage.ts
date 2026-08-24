import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { useUsageLimitsStore } from "@/store/useUsageLimitsStore";
import type { UsageLimits } from "@/types/api";

export const USAGE_QUERY_KEY = ["usage"] as const;

/**
 * USD budget per account (`profiles.usage_budget_usd`, ADR-16) + current period usage.
 * Feeds `useUsageLimitsStore` ("90% of budget" badge). Also refreshed after 429
 * (`useChatStream` calls `queryClient.invalidateQueries(USAGE_QUERY_KEY)`).
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
