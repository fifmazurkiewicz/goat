import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { endOfWeek } from "date-fns";

import { useAllResults } from "@/hooks/useResults";
import { planRangeKey } from "@/hooks/usePlans";
import { apiFetch } from "@/lib/api-client";
import { logRangeStart, monthRanges } from "@/lib/training-log";
import type { PlanItem, PlanRangeResponse } from "@/types/api";

/**
 * Data for the "since start" log: all results (already cached for `/results` tabs)
 * + one `GET /plans` range per month — same keys as the month calendar, so the cache is shared.
 */
export function useTrainingLogData(today: Date) {
  const { data: results, isLoading: resultsLoading } = useAllResults();
  const start = useMemo(() => logRangeStart(results ?? [], today), [results, today]);
  const ranges = useMemo(() => monthRanges(start, endOfWeek(today, { weekStartsOn: 1 })), [start, today]);

  const planQueries = useQueries({
    queries: ranges.map(({ startDate, endDate }) => ({
      queryKey: planRangeKey(startDate, endDate),
      queryFn: () => apiFetch<PlanRangeResponse>(`/api/v1/plans?start_date=${startDate}&end_date=${endDate}`),
      enabled: !resultsLoading,
    })),
  });

  const plansLoading = planQueries.some((query) => query.isLoading);
  const itemsKey = planQueries.map((query) => query.dataUpdatedAt).join(",");
  const items = useMemo<PlanItem[]>(
    () => planQueries.flatMap((query) => query.data?.items ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `useQueries` returns a new array every render
    [itemsKey]
  );

  return { start, items, results: results ?? [], isLoading: resultsLoading || plansLoading };
}
