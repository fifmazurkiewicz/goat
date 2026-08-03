import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiFetch } from "@/lib/api-client";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";
import type { GeneratePlanInput, GeneratePlanResponse, PlanGenerationJob, PlanRangeResponse } from "@/types/api";

export function planRangeKey(startDate: string, endDate: string) {
  return ["plans", startDate, endDate] as const;
}

/** `GET /plans?start_date=&end_date=` — plan + plan_items dla widocznego zakresu kalendarza. */
export function usePlanRange(startDate: string, endDate: string) {
  return useQuery({
    queryKey: planRangeKey(startDate, endDate),
    queryFn: () =>
      apiFetch<PlanRangeResponse>(`/api/v1/plans?start_date=${startDate}&end_date=${endDate}`),
  });
}

export function useGeneratePlan() {
  const queryClient = useQueryClient();
  const startJob = usePlanGenerationStore((state) => state.startJob);

  return useMutation({
    mutationFn: (input: GeneratePlanInput) =>
      apiFetch<GeneratePlanResponse>("/api/v1/plans/generate", { method: "POST", body: input }),
    onSuccess: (data) => {
      startJob(data.job_id);
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
  });
}

const POLL_INTERVAL_MS = 4000;

/**
 * Polling `GET /plans/jobs/{id}` — MOUNTOWANY W APP SHELL, nie w /plans
 * (docs/technical/frontend.md sekcja 2 i 5). `/plans` czyta tylko wynikowy stan z
 * `usePlanGenerationStore`, nigdy nie odpytuje samo. Side-effect (toast) żyje tutaj,
 * w miejscu gdzie żyje polling — nie w komponencie strony.
 */
export function usePlanGenerationPolling() {
  const jobId = usePlanGenerationStore((state) => state.jobId);
  const status = usePlanGenerationStore((state) => state.status);
  const setStatus = usePlanGenerationStore((state) => state.setStatus);
  const queryClient = useQueryClient();
  const lastNotifiedStatus = useRef(status);

  useEffect(() => {
    if (!jobId || status !== "generating") return;

    let cancelled = false;
    const interval = setInterval(async () => {
      try {
        const job = await apiFetch<PlanGenerationJob>(`/api/v1/plans/jobs/${jobId}`);
        if (cancelled) return;

        if (job.status === "pending" || job.status === "running") return;

        const nextStatus =
          job.status === "success" ? "ready" : job.status === "partial_success" ? "partial_ready" : "error";
        setStatus(nextStatus, job.breakdown);
        void queryClient.invalidateQueries({ queryKey: ["plans"] });
      } catch {
        // Błąd sieci przy pollingu — spróbujemy ponownie przy kolejnym ticku, bez
        // przerywania stanu "generating" (odróżnij od faktycznego statusu jobu).
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [jobId, status, setStatus, queryClient]);

  useEffect(() => {
    if (lastNotifiedStatus.current === status) return;
    lastNotifiedStatus.current = status;

    if (status === "ready") {
      toast.success("Plan gotowy", { description: "Nowy plan został wygenerowany." });
    } else if (status === "partial_ready") {
      toast.warning("Plan częściowo gotowy", {
        description: "Dla części person generowanie się nie udało — możesz spróbować ponownie.",
      });
    } else if (status === "error") {
      toast.error("Generowanie planu nie powiodło się", {
        description: "Spróbuj wygenerować plan ponownie.",
      });
    }
  }, [status]);
}
