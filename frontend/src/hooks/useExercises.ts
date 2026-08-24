import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { Exercise } from "@/types/api";

/**
 * `GET /exercises` (ADR-14) — reference data, long `staleTime` (changes only
 * when a new migration is deployed). Filtering by category/query is done
 * CLIENT-SIDE (docs/technical/frontend.md section 7a) — after importing
 * free-exercise-db ~870 items; useMemo + `useDeferredValue` filter holds up
 * without a round-trip, payload is compressed by GZipMiddleware on the API side.
 */
export function useExercises() {
  return useQuery({
    queryKey: ["exercises"],
    staleTime: 60 * 60 * 1000,
    queryFn: () => apiFetch<Exercise[]>("/api/v1/exercises"),
  });
}
