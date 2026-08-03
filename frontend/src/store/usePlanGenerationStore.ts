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
    // localStorage niedostępny (np. tryb prywatny) — brak persystencji, nie krytyczne.
  }
}

/**
 * Mountowany w app shell / root layout (nie w /plans) — patrz
 * docs/technical/frontend.md sekcja 2. Odtwarza `jobId` z localStorage przy
 * starcie, żeby polling przetrwał zamknięcie karty. Właściwy polling
 * (GET /plans/jobs/{id}) i side-effecty (toasty) będą podpięte w kolejnym
 * etapie, w miejscu gdzie ten store jest mountowany.
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
    if (status === "ready" || status === "error" || status === "idle") {
      persistJobId(null);
    }
    set((state) => ({ status, breakdown: breakdown ?? state.breakdown }));
  },
  reset: () => {
    persistJobId(null);
    set({ status: "idle", jobId: null, startedAt: null, breakdown: [] });
  },
}));
