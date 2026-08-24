import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { Result, ResultCategory } from "@/types/api";

export function resultsKey(category: ResultCategory) {
  return ["results", category] as const;
}

export const ALL_RESULTS_KEY = ["results", "all"] as const;

/**
 * All user results (no category filter) — used to build tabs when the agent
 * logged an entry in a category outside persona mapping (e.g. triathlon with only motor_coach).
 */
export function useAllResults() {
  return useQuery({
    queryKey: ALL_RESULTS_KEY,
    queryFn: () => apiFetch<Result[]>("/api/v1/results"),
  });
}

/**
 * `GET /results?category=` — the `results_user_category_metric_date` index
 * supports this query (docs/technical/frontend.md section 6, ADR-9). Filtering by
 * metric for the chart is done client-side on the already-fetched category results
 * (dozens of entries at most, no need for a separate request per metric).
 */
export function useResults(category: ResultCategory | null | undefined) {
  return useQuery({
    queryKey: resultsKey(category ?? "strength"),
    queryFn: () =>
      apiFetch<Result[]>(`/api/v1/results?category=${encodeURIComponent(category!)}`),
    enabled: Boolean(category),
  });
}

/**
 * Results logged on a SPECIFIC day (all categories) — `ActualResultsPanel` in
 * `/plans` (ADR-9: "Completed" next to "Planned", a simple plan vs results juxtaposition).
 */
export function useResultsByDate(date: string | undefined) {
  return useQuery({
    queryKey: ["results", "by-date", date],
    queryFn: () =>
      apiFetch<Result[]>(
        `/api/v1/results?date_from=${encodeURIComponent(date!)}&date_to=${encodeURIComponent(date!)}`
      ),
    enabled: Boolean(date),
  });
}

export interface ResultCreateInput {
  category: ResultCategory;
  metric: string;
  value: number;
  unit: string;
  logged_date: string;
  notes?: string | null;
}

export function useCreateResult() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ResultCreateInput) => apiFetch<Result>("/api/v1/results", { method: "POST", body: input }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["results"] });
      void queryClient.invalidateQueries({ queryKey: resultsKey(result.category) });
    },
  });
}

export interface ResultUpdateInput {
  value?: number;
  unit?: string;
  logged_date?: string;
  notes?: string | null;
}

export function useUpdateResult(category: ResultCategory) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: ResultUpdateInput }) =>
      apiFetch<Result>(`/api/v1/results/${id}`, { method: "PATCH", body: input }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: resultsKey(category) });
      void queryClient.invalidateQueries({ queryKey: ALL_RESULTS_KEY });
    },
  });
}

export function useDeleteResult(category: ResultCategory) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/api/v1/results/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: resultsKey(category) });
      void queryClient.invalidateQueries({ queryKey: ALL_RESULTS_KEY });
    },
  });
}
