export const API_HEALTH_WAKING_AFTER_MS = 2_000;
export const API_HEALTH_DOWN_AFTER_MS = 90_000;
export const API_HEALTH_ATTEMPT_TIMEOUT_MS = 8_000;
export const API_HEALTH_RETRY_EVERY_MS = 4_000;

export type ApiHealthLampState = "hidden" | "waking" | "down";

export interface WakeWindowState {
  open: boolean;
  startedAt: number | null;
  succeeded: boolean;
  autoStopped: boolean;
  inFlight: boolean;
  nextProbeAt: number | null;
}

export function initialWakeState(): WakeWindowState {
  return {
    open: false,
    startedAt: null,
    succeeded: false,
    autoStopped: false,
    inFlight: false,
    nextProbeAt: null,
  };
}

/** Idempotentne, gdy okno już leci. Tap po `down` resetuje licznik. */
export function openWakeWindow(
  state: WakeWindowState,
  now: number,
  opts?: { force?: boolean }
): WakeWindowState {
  if (state.open && !state.autoStopped && !state.succeeded) {
    return state;
  }
  if (state.succeeded && !opts?.force) {
    return state;
  }
  return {
    open: true,
    startedAt: now,
    succeeded: false,
    autoStopped: false,
    inFlight: false,
    nextProbeAt: now,
  };
}

export function closeWakeWindow(_state: WakeWindowState): WakeWindowState {
  return initialWakeState();
}

export function markProbeStarted(state: WakeWindowState): WakeWindowState {
  return { ...state, inFlight: true, nextProbeAt: null };
}

export function markHealthResult(
  state: WakeWindowState,
  now: number,
  ok: boolean
): WakeWindowState {
  if (ok) {
    return {
      open: false,
      startedAt: state.startedAt,
      succeeded: true,
      autoStopped: false,
      inFlight: false,
      nextProbeAt: null,
    };
  }

  const startedAt = state.startedAt ?? now;
  if (now - startedAt >= API_HEALTH_DOWN_AFTER_MS) {
    return {
      ...state,
      autoStopped: true,
      inFlight: false,
      nextProbeAt: null,
    };
  }

  return {
    ...state,
    inFlight: false,
    nextProbeAt: now + API_HEALTH_RETRY_EVERY_MS,
  };
}

export function lampState(state: WakeWindowState, now: number): ApiHealthLampState {
  if (!state.open || state.succeeded || state.startedAt === null) return "hidden";
  const elapsed = now - state.startedAt;
  if (state.autoStopped || elapsed >= API_HEALTH_DOWN_AFTER_MS) return "down";
  if (elapsed >= API_HEALTH_WAKING_AFTER_MS) return "waking";
  return "hidden";
}

export function lampMessage(state: ApiHealthLampState): string | null {
  if (state === "waking") return "Budzimy aplikację, poczekaj chwilę.";
  if (state === "down") return "Nie możemy połączyć się z serwerem. Spróbujemy ponownie.";
  return null;
}

export function shouldProbeHealth(
  state: WakeWindowState,
  now: number,
  visible: boolean
): boolean {
  if (!state.open || state.succeeded || state.autoStopped || !visible || state.inFlight) {
    return false;
  }
  if (state.startedAt !== null && now - state.startedAt >= API_HEALTH_DOWN_AFTER_MS) {
    return false;
  }
  if (state.nextProbeAt === null) return false;
  return now >= state.nextProbeAt;
}

export function isNetworkError(err: unknown): boolean {
  if (err instanceof Error && err.name === "ApiError") return false;
  if (typeof DOMException !== "undefined" && err instanceof DOMException && err.name === "AbortError") {
    return false;
  }
  if (err instanceof Error && err.name === "AbortError") return false;
  if (err instanceof TypeError) return true;
  if (err instanceof Error && /failed to fetch|networkerror|load failed|fetch failed/i.test(err.message)) {
    return true;
  }
  return false;
}
