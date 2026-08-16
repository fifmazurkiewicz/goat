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
  it("ukrywa lampkę gdy okno zamknięte albo tuż po starcie (< 2 s)", () => {
    expect(lampState(initialWakeState(), 0)).toBe("hidden");
    const opened = openWakeWindow(initialWakeState(), 1_000);
    expect(lampState(opened, 1_000)).toBe("hidden");
    expect(lampState(opened, 1_000 + API_HEALTH_WAKING_AFTER_MS - 1)).toBe("hidden");
    expect(lampMessage("hidden")).toBeNull();
  });

  it("po ≥ 2 s bez sukcesu pokazuje waking i tekst o budzeniu", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    expect(lampState(opened, API_HEALTH_WAKING_AFTER_MS)).toBe("waking");
    expect(lampMessage("waking")).toBe("Budzimy aplikację, poczekaj chwilę.");
  });

  it("po ≥ 90 s pokazuje down i tekst o braku połączenia", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    expect(lampState(opened, API_HEALTH_DOWN_AFTER_MS)).toBe("down");
    expect(lampMessage("down")).toBe("Nie możemy połączyć się z serwerem. Spróbujemy ponownie.");
  });

  it("po sukcesie lampka znika", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    const ok = markHealthResult(opened, 3_000, true);
    expect(lampState(ok, 3_000)).toBe("hidden");
    expect(ok.open).toBe(false);
  });
});

describe("shouldProbeHealth", () => {
  it("pierwsza próba idzie od razu po otwarciu okna, gdy karta widoczna", () => {
    const opened = openWakeWindow(initialWakeState(), 10);
    expect(shouldProbeHealth(opened, 10, true)).toBe(true);
  });

  it("nie sondy gdy karta w tle", () => {
    const opened = openWakeWindow(initialWakeState(), 10);
    expect(shouldProbeHealth(opened, 10, false)).toBe(false);
  });

  it("nie sondy gdy request już leci albo sukces", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    const inFlight = markProbeStarted(opened);
    expect(shouldProbeHealth(inFlight, 100, true)).toBe(false);

    const ok = markHealthResult(opened, 100, true);
    expect(shouldProbeHealth(ok, 200, true)).toBe(false);
  });

  it("po nieudanej próbie czeka 4 s, potem znowu; po 90 s stop automatu", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    const failed = markHealthResult(markProbeStarted(opened), 1_000, false);
    expect(shouldProbeHealth(failed, 1_000, true)).toBe(false);
    expect(shouldProbeHealth(failed, 1_000 + API_HEALTH_RETRY_EVERY_MS, true)).toBe(true);

    const lateFail = markHealthResult(markProbeStarted(opened), API_HEALTH_DOWN_AFTER_MS, false);
    expect(lateFail.autoStopped).toBe(true);
    expect(shouldProbeHealth(lateFail, API_HEALTH_DOWN_AFTER_MS + 10_000, true)).toBe(false);
  });

  it("po 90 s nie sondy nawet gdy autoStopped jeszcze nie ustawione", () => {
    const waiting = markHealthResult(markProbeStarted(openWakeWindow(initialWakeState(), 0)), 1_000, false);
    expect(waiting.autoStopped).toBe(false);
    expect(shouldProbeHealth(waiting, API_HEALTH_DOWN_AFTER_MS, true)).toBe(false);
  });

  it("zamknięcie okna (karta w tle) i sukces = zero dalszych prób", () => {
    const opened = openWakeWindow(initialWakeState(), 0);
    expect(shouldProbeHealth(closeWakeWindow(opened), 5_000, true)).toBe(false);
  });

  it("tap po down otwiera nowe okno i znowu pozwala sondować", () => {
    const down = markHealthResult(
      markProbeStarted(openWakeWindow(initialWakeState(), 0)),
      API_HEALTH_DOWN_AFTER_MS,
      false
    );
    const retried = openWakeWindow(down, API_HEALTH_DOWN_AFTER_MS + 5_000);
    expect(retried.autoStopped).toBe(false);
    expect(shouldProbeHealth(retried, API_HEALTH_DOWN_AFTER_MS + 5_000, true)).toBe(true);
  });

  it("po sukcesie nie otwiera okna ponownie, chyba że force (błąd sieci)", () => {
    const ok = markHealthResult(openWakeWindow(initialWakeState(), 0), 100, true);
    expect(openWakeWindow(ok, 200).open).toBe(false);
    const forced = openWakeWindow(ok, 200, { force: true });
    expect(forced.open).toBe(true);
    expect(shouldProbeHealth(forced, 200, true)).toBe(true);
  });
});

describe("isNetworkError", () => {
  it("łapie TypeError / Failed to fetch, nie ApiError ani AbortError", () => {
    expect(isNetworkError(new TypeError("Failed to fetch"))).toBe(true);
    expect(isNetworkError(new ApiError("not_found", "brak", 404))).toBe(false);
    expect(isNetworkError(new DOMException("Aborted", "AbortError"))).toBe(false);
  });
});
