import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import {
  API_HEALTH_DOWN_AFTER_MS,
  API_HEALTH_RETRY_EVERY_MS,
  API_HEALTH_WAKING_AFTER_MS,
  closeWakeWindow,
  initialWakeState,
  isNetworkError,
  lampMessage,
  lampState,
  markHealthResult,
  markProbeStarted,
  openWakeWindow,
  shouldProbeHealth,
} from "@/lib/api-health";

describe("lampState / lampMessage", () => {
  it("hides the lamp when the window is closed or just opened (< 2 s)", () => {
    expect(lampState(initialWakeState(), 0)).toBe("hidden");
    const opened = openWakeWindow(initialWakeState(), 1_000);
    expect(lampState(opened, 1_000)).toBe("hidden");
    expect(lampState(opened, 1_000 + API_HEALTH_WAKING_AFTER_MS - 1)).toBe("hidden");
    expect(lampMessage("hidden")).toBeNull();
  });

  it("after ≥ 2 s without success shows waking and the wake-up message", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    expect(lampState(opened, API_HEALTH_WAKING_AFTER_MS)).toBe("waking");
    expect(lampMessage("waking")).toBe("Budzimy aplikację, poczekaj chwilę.");
  });

  it("after ≥ 90 s shows down and the connection-lost message", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    expect(lampState(opened, API_HEALTH_DOWN_AFTER_MS)).toBe("down");
    expect(lampMessage("down")).toBe("Nie możemy połączyć się z serwerem. Spróbujemy ponownie.");
  });

  it("hides the lamp after success", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    const ok = markHealthResult(opened, 3_000, true);
    expect(lampState(ok, 3_000)).toBe("hidden");
    expect(ok.open).toBe(false);
  });
});

describe("shouldProbeHealth", () => {
  it("first probe runs immediately after opening the window, when the tab is visible", () => {
    const opened = openWakeWindow(initialWakeState(), 10);
    expect(shouldProbeHealth(opened, 10, true)).toBe(true);
  });

  it("does not probe when the tab is in the background", () => {
    const opened = openWakeWindow(initialWakeState(), 10);
    expect(shouldProbeHealth(opened, 10, false)).toBe(false);
  });

  it("does not probe when a request is in flight or already succeeded", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    const inFlight = markProbeStarted(opened);
    expect(shouldProbeHealth(inFlight, 100, true)).toBe(false);

    const ok = markHealthResult(opened, 100, true);
    expect(shouldProbeHealth(ok, 200, true)).toBe(false);
  });

  it("waits 4 s after a failed probe, then retries; auto-stops after 90 s", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    const failed = markHealthResult(markProbeStarted(opened), 1_000, false);
    expect(shouldProbeHealth(failed, 1_000, true)).toBe(false);
    expect(shouldProbeHealth(failed, 1_000 + API_HEALTH_RETRY_EVERY_MS, true)).toBe(true);

    const lateFail = markHealthResult(markProbeStarted(opened), API_HEALTH_DOWN_AFTER_MS, false);
    expect(lateFail.autoStopped).toBe(true);
    expect(shouldProbeHealth(lateFail, API_HEALTH_DOWN_AFTER_MS + 10_000, true)).toBe(false);
  });

  it("does not probe after 90 s even if autoStopped is not yet set", () => {
    const waiting = markHealthResult(markProbeStarted(openWakeWindow(initialWakeState(), 0)), 1_000, false);
    expect(waiting.autoStopped).toBe(false);
    expect(shouldProbeHealth(waiting, API_HEALTH_DOWN_AFTER_MS, true)).toBe(false);
  });

  it("closing the window (background tab) and success = no further probes", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    expect(shouldProbeHealth(closeWakeWindow(opened), 5_000, true)).toBe(false);
  });

  it("a tap after down opens a new window and resumes probing", () => {
    const down = markHealthResult(
      markProbeStarted(openWakeWindow(initialWakeState(), 0)),
      API_HEALTH_DOWN_AFTER_MS,
      false
    );
    const retried = openWakeWindow(down, API_HEALTH_DOWN_AFTER_MS + 5_000);
    expect(retried.autoStopped).toBe(false);
    expect(shouldProbeHealth(retried, API_HEALTH_DOWN_AFTER_MS + 5_000, true)).toBe(true);
  });

  it("does not re-open the window after success, unless forced (network error)", () => {
    const ok = markHealthResult(openWakeWindow(initialWakeState(), 0), 100, true);
    expect(openWakeWindow(ok, 200).open).toBe(false);
    const forced = openWakeWindow(ok, 200, { force: true });
    expect(forced.open).toBe(true);
    expect(shouldProbeHealth(forced, 200, true)).toBe(true);
  });
});

describe("isNetworkError", () => {
  it("catches TypeError / Failed to fetch, not ApiError or AbortError", () => {
    expect(isNetworkError(new TypeError("Failed to fetch"))).toBe(true);
    expect(isNetworkError(new ApiError("not_found", "brak", 404))).toBe(false);
    expect(isNetworkError(new DOMException("Aborted", "AbortError"))).toBe(false);
  });
});
