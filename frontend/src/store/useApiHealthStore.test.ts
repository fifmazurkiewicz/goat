import { afterEach, describe, expect, it, vi } from "vitest";

import { API_HEALTH_WAKING_AFTER_MS } from "@/lib/api-health";
import { useApiHealthStore, watchSlowApiRequest } from "@/store/useApiHealthStore";

describe("watchSlowApiRequest", () => {
  afterEach(() => {
    vi.useRealTimers();
    useApiHealthStore.getState().closeWakeWindow();
  });

  it("does not reopen a successful wake window for another slow request", () => {
    vi.useFakeTimers();

    watchSlowApiRequest();
    vi.advanceTimersByTime(API_HEALTH_WAKING_AFTER_MS);
    useApiHealthStore.getState().markHealthResult(true);

    watchSlowApiRequest();
    vi.advanceTimersByTime(API_HEALTH_WAKING_AFTER_MS);

    expect(useApiHealthStore.getState().wake.open).toBe(false);
  });
});
