import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { Result, ResultCategory } from "@/types/api";

export function resultsKey(category: ResultCategory) {
  return ["results", category] as const;
}

/**
 * `GET /results?category=&metric=` — indeks `results_user_category_metric_date`
 * wspiera to zapytanie (docs/technical/frontend.md sekcja 6, ADR-9). Filtrowanie po
 * metryce dla wykresu robione po stronie klienta na już pobranych wynikach kategorii
 * (rząd dziesiątek wpisów, brak potrzeby osobnego requestu per metryka).
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
 * Wyniki zalogowane KONKRETNEGO dnia (wszystkie kategorie) — `ActualResultsPanel` w
 * `/plans` (ADR-9: "Zrealizowane" obok "Zaplanowane", prosta juxtapozycja plan vs wyniki).
 */
export function useResultsByDate(date: string | undefined) {
  return useQuery({
    queryKey: ["results", "by-date", date],
    queryFn: () => apiFetch<Result[]>(`/api/v1/results?from=${date}&to=${date}`),
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
    },
  });
}

export function useDeleteResult(category: ResultCategory) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/api/v1/results/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: resultsKey(category) });
    },
  });
}
