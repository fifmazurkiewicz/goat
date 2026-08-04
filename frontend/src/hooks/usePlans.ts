import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiFetch, ApiError } from "@/lib/api-client";
import { useAuthStore } from "@/store/useAuthStore";
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
      const jobId = data.job_id ?? data.id;
      startJob(jobId);
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
  });
}

const POLL_INTERVAL_MS = 4000;

function applyActiveJob(job: PlanGenerationJob) {
  const startJob = usePlanGenerationStore.getState().startJob;
  const updateProgress = usePlanGenerationStore.getState().updateProgress;
  startJob(job.id);
  const breakdown = job.personas ?? job.breakdown;
  if (breakdown?.length) {
    updateProgress(breakdown);
  }
}

/** Pobiera aktywny job z backendu (gdy localStorage/store nie wiedzą o trwającym generowaniu). */
export async function syncActivePlanJob(): Promise<PlanGenerationJob | null> {
  const job = await apiFetch<PlanGenerationJob | null>("/api/v1/plans/jobs/active");
  if (job && (job.status === "pending" || job.status === "running")) {
    applyActiveJob(job);
    return job;
  }
  return null;
}

export function useCancelPlanJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      apiFetch<PlanGenerationJob>(`/api/v1/plans/jobs/${jobId}/cancel`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
  });
}

/**
 * Przy starcie appki synchronizuje aktywny job z backendu — naprawia sytuację
 * „Masz już aktywny job” bez widocznego banera (utracony localStorage).
 */
export function usePlanGenerationSync() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());

  useEffect(() => {
    if (!isAuthenticated) return;

    void syncActivePlanJob().catch(() => {
      // Brak aktywnego joba — normalny stan idle.
    });
  }, [isAuthenticated]);
}

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
  const updateProgress = usePlanGenerationStore((state) => state.updateProgress);
  const queryClient = useQueryClient();
  const lastNotifiedStatus = useRef(status);

  useEffect(() => {
    if (!jobId || status !== "generating") return;

    let cancelled = false;

    async function pollOnce() {
      try {
        const job = await apiFetch<PlanGenerationJob>(`/api/v1/plans/jobs/${jobId}`);
        if (cancelled) return;

        const breakdown = job.personas ?? job.breakdown;
        if (breakdown?.length) {
          updateProgress(breakdown);
        }

        if (job.status === "pending" || job.status === "running") return;

        const nextStatus =
          job.status === "success" ? "ready" : job.status === "partial_success" ? "partial_ready" : "error";
        setStatus(nextStatus, breakdown);
        void queryClient.invalidateQueries({ queryKey: ["plans"] });
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setStatus("error");
        }
      }
    }

    void pollOnce();
    const interval = setInterval(() => void pollOnce(), POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [jobId, status, setStatus, updateProgress, queryClient]);

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
