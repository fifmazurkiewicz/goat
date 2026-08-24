import { create } from "zustand";
import type { PlanGenerationJobPersonaBreakdown } from "@/types/api";

export type PlanGenerationStatus =
  | "idle"
  | "generating"
  | "ready"
  | "partial_ready"
  | "error";

interface PlanGenerationState {
  status: PlanGenerationStatus;
  jobId: string | null;
  startedAt: string | null;
  breakdown: PlanGenerationJobPersonaBreakdown[];
  startJob: (jobId: string) => void;
  setStatus: (status: PlanGenerationStatus, breakdown?: PlanGenerationJobPersonaBreakdown[]) => void;
  updateProgress: (breakdown: PlanGenerationJobPersonaBreakdown[]) => void;
  reset: () => void;
}

const STORAGE_KEY = "coach.planGeneration.jobId";

function readPersistedJobId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistJobId(jobId: string | null) {
  try {
    if (jobId) {
      localStorage.setItem(STORAGE_KEY, jobId);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // localStorage unavailable (e.g. private mode) — no persistence, not critical.
  }
}

/**
 * Mounted in the app shell / root layout (not in /plans) — see
 * docs/technical/frontend.md section 2. Restores `jobId` from localStorage at
 * startup, so polling survives closing the tab. The actual polling
 * (GET /plans/jobs/{id}) and side effects (toasts) will be wired up in a later
 * step, in the place where this store is mounted.
 */
export const usePlanGenerationStore = create<PlanGenerationState>((set) => ({
  status: readPersistedJobId() ? "generating" : "idle",
  jobId: readPersistedJobId(),
  startedAt: null,
  breakdown: [],
  startJob: (jobId) => {
    persistJobId(jobId);
    set({ status: "generating", jobId, startedAt: new Date().toISOString(), breakdown: [] });
  },
  setStatus: (status, breakdown) => {
    if (status === "ready" || status === "partial_ready" || status === "error" || status === "idle") {
      persistJobId(null);
    }
    set((state) => ({ status, breakdown: breakdown ?? state.breakdown }));
  },
  updateProgress: (breakdown) => set({ breakdown }),
  reset: () => {
    persistJobId(null);
    set({ status: "idle", jobId: null, startedAt: null, breakdown: [] });
  },
}));
