import { beforeEach, describe, expect, it } from "vitest";

import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";

function resetStore() {
  usePlanGenerationStore.getState().reset();
}

describe("usePlanGenerationStore", () => {
  beforeEach(() => {
    localStorage.clear();
    resetStore();
  });

  it("zaczyna w stanie idle bez zapisanego jobId", () => {
    expect(usePlanGenerationStore.getState().status).toBe("idle");
    expect(usePlanGenerationStore.getState().jobId).toBeNull();
  });

  it("startJob przełącza w stan generating i zapisuje jobId w localStorage", () => {
    usePlanGenerationStore.getState().startJob("job-1");

    const state = usePlanGenerationStore.getState();
    expect(state.status).toBe("generating");
    expect(state.jobId).toBe("job-1");
    expect(localStorage.getItem("coach.planGeneration.jobId")).toBe("job-1");
  });

  it("setStatus('ready') czyści jobId z localStorage, ale zachowuje go w stanie", () => {
    usePlanGenerationStore.getState().startJob("job-1");
    usePlanGenerationStore.getState().setStatus("ready");

    expect(usePlanGenerationStore.getState().status).toBe("ready");
    expect(localStorage.getItem("coach.planGeneration.jobId")).toBeNull();
  });

  it("setStatus('partial_ready') zapisuje breakdown person i czyści localStorage", () => {
    usePlanGenerationStore.getState().startJob("job-1");
    usePlanGenerationStore.getState().setStatus("partial_ready", [
      { persona_id: "p1", status: "done", retry_count: 0, last_error: null },
      { persona_id: "p2", status: "failed", retry_count: 2, last_error: "timeout" },
    ]);

    const state = usePlanGenerationStore.getState();
    expect(state.status).toBe("partial_ready");
    expect(state.breakdown).toHaveLength(2);
    expect(state.breakdown[1].status).toBe("failed");
    expect(localStorage.getItem("coach.planGeneration.jobId")).toBeNull();
  });

  it("setStatus('error') czyści persystencję jobId", () => {
    usePlanGenerationStore.getState().startJob("job-1");
    usePlanGenerationStore.getState().setStatus("error");

    expect(usePlanGenerationStore.getState().status).toBe("error");
    expect(localStorage.getItem("coach.planGeneration.jobId")).toBeNull();
  });

  it("reset wraca do stanu idle i czyści breakdown", () => {
    usePlanGenerationStore.getState().startJob("job-1");
    usePlanGenerationStore.getState().setStatus("partial_ready", [
      { persona_id: "p1", status: "failed", retry_count: 1, last_error: "boom" },
    ]);

    usePlanGenerationStore.getState().reset();

    const state = usePlanGenerationStore.getState();
    expect(state.status).toBe("idle");
    expect(state.jobId).toBeNull();
    expect(state.breakdown).toHaveLength(0);
  });
});
