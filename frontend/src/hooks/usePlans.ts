import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiFetch, ApiError } from "@/lib/api-client";
import { streamPlanJobEvents } from "@/lib/sse";
import { useAuthStore } from "@/store/useAuthStore";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";
import type { GeneratePlanInput, GeneratePlanResponse, PlanGenerationJob, PlanRangeResponse } from "@/types/api";

export function planRangeKey(startDate: string, endDate: string) {
  return ["plans", startDate, endDate] as const;
}

/** `GET /plans?start_date=&end_date=` — plan + plan_items for the visible calendar range. */
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

/** Fetches the active job from the backend (when localStorage/store don't know about an in-progress generation). */
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
 * On app startup, synchronizes the active job from the backend — fixes the
 * "You already have an active job" state without a visible banner (lost localStorage).
 */
export function usePlanGenerationSync() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());

  useEffect(() => {
    if (!isAuthenticated) return;

    void syncActivePlanJob().catch(() => {
      // No active job — normal idle state.
    });
  }, [isAuthenticated]);
}

/**
 * Polling `GET /plans/jobs/{id}` — MOUNTED IN APP SHELL, not in /plans
 * (docs/technical/frontend.md sections 2 and 5). `/plans` only reads the resulting
 * state from `usePlanGenerationStore`, it never polls on its own. The side-effect
 * (toast) lives here, where the polling lives — not in the page component.
 */
export function usePlanGenerationPolling() {
  const jobId = usePlanGenerationStore((state) => state.jobId);
  const status = usePlanGenerationStore((state) => state.status);
  const setStatus = usePlanGenerationStore((state) => state.setStatus);
  const updateProgress = usePlanGenerationStore((state) => state.updateProgress);
  const setPhase = usePlanGenerationStore((state) => state.setPhase);
  const queryClient = useQueryClient();
  const lastNotifiedStatus = useRef(status);
  const lastDoneCount = useRef(0);

  useEffect(() => {
    if (!jobId || status !== "generating") return;
    const activeJobId = jobId;

    const controller = new AbortController();
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let retrying = false;

    function applyJob(job: PlanGenerationJob) {
      const breakdown = job.personas ?? job.breakdown;
      if (breakdown?.length) {
        updateProgress(breakdown);
        const doneCount = breakdown.filter((p) => p.status === "done" || p.status === "failed").length;
        if (doneCount > lastDoneCount.current) {
          lastDoneCount.current = doneCount;
          void queryClient.invalidateQueries({ queryKey: ["plans"] });
        }
      }
      if (job.status === "pending" || job.status === "running") return;

      const nextStatus =
        job.status === "success" ? "ready" : job.status === "partial_success" ? "partial_ready" : "error";
      setStatus(nextStatus, breakdown);
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
    }

    async function pollFallback() {
      if (retrying || controller.signal.aborted) return;
      retrying = true;
      try {
        const job = await apiFetch<PlanGenerationJob>(`/api/v1/plans/jobs/${activeJobId}`);
        if (!controller.signal.aborted) applyJob(job);
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof ApiError && err.status === 404) {
          setStatus("error");
        }
      } finally {
        retrying = false;
      }
    }

    async function consumeEvents() {
      try {
        for await (const event of streamPlanJobEvents({ jobId: activeJobId, signal: controller.signal })) {
          if (controller.signal.aborted) return;
          setPhase(event.phase);
          applyJob(event);
        }
        if (!controller.signal.aborted && usePlanGenerationStore.getState().status === "generating") {
          retryTimer = setTimeout(() => void consumeEvents(), POLL_INTERVAL_MS);
        }
      } catch {
        if (!controller.signal.aborted) {
          await pollFallback();
          if (!controller.signal.aborted && usePlanGenerationStore.getState().status === "generating") {
            retryTimer = setTimeout(() => void consumeEvents(), POLL_INTERVAL_MS);
          }
        }
      }
    }

    lastDoneCount.current = 0;
    void consumeEvents();
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") void pollFallback();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      controller.abort();
      if (retryTimer) clearTimeout(retryTimer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [jobId, status, setStatus, updateProgress, setPhase, queryClient]);

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
