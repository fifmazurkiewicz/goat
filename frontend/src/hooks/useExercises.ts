import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { Exercise } from "@/types/api";

/**
 * `GET /exercises` (ADR-14) — treść referencyjna, `staleTime` długi (zmienia się
 * wyłącznie przy deployu nowej migracji). Filtrowanie po kategorii/query robione
 * PO STRONIE KLIENTA (docs/technical/frontend.md sekcja 7a) — katalog rzędu
 * kilkudziesięciu pozycji, brak potrzeby round-tripu przy każdej zmianie filtra.
 */
export function useExercises() {
  return useQuery({
    queryKey: ["exercises"],
    staleTime: 60 * 60 * 1000,
    queryFn: () => apiFetch<Exercise[]>("/api/v1/exercises"),
  });
}
