import { create } from "zustand";

import {
  API_HEALTH_WAKING_AFTER_MS,
  closeWakeWindow,
  initialWakeState,
  isNetworkError,
  lampState,
  markHealthResult,
  markProbeStarted,
  openWakeWindow,
  type ApiHealthLampState,
  type WakeWindowState,
} from "@/lib/api-health";

interface ApiHealthStore {
  wake: WakeWindowState;
  now: number;
  lamp: ApiHealthLampState;
  startWakeWindow: (opts?: { force?: boolean }) => void;
  closeWakeWindow: () => void;
  markProbeStarted: () => void;
  markHealthResult: (ok: boolean) => void;
  tick: (now?: number) => void;
}

function snapshot(wake: WakeWindowState, now: number) {
  return { wake, now, lamp: lampState(wake, now) };
}

/**
 * State of the Render wake window (ADR-19). The HTTP probe lives in `useApiHealthProbe`;
 * `apiFetch` calls `startWakeWindow({ force: true })` on a network error.
 */
export const useApiHealthStore = create<ApiHealthStore>((set, get) => ({
  ...snapshot(initialWakeState(), 0),

  startWakeWindow: (opts) => {
    const now = Date.now();
    set(snapshot(openWakeWindow(get().wake, now, opts), now));
  },

  closeWakeWindow: () => {
    set(snapshot(closeWakeWindow(get().wake), Date.now()));
  },

  markProbeStarted: () => {
    const now = Date.now();
    set(snapshot(markProbeStarted(get().wake), now));
  },

  markHealthResult: (ok) => {
    const now = Date.now();
    set(snapshot(markHealthResult(get().wake, now, ok), now));
  },

  tick: (now = Date.now()) => {
    set(snapshot(get().wake, now));
  },
}));

/** Real network error in an actual request — new wake window, not a 4xx/Abort. */
export function reportApiNetworkError(err: unknown): void {
  if (isNetworkError(err)) {
    useApiHealthStore.getState().startWakeWindow({ force: true });
  }
}

/**
 * If a real request hangs for ≥ 2s, opens the wake window (cold start after idle).
 * Call the returned `finish(ok)` after the fetch completes — on success it clears the lamp.
 */
export function watchSlowApiRequest(): (ok: boolean) => void {
  const timeoutId = window.setTimeout(() => {
    useApiHealthStore.getState().startWakeWindow();
  }, API_HEALTH_WAKING_AFTER_MS);

  return (ok: boolean) => {
    window.clearTimeout(timeoutId);
    if (ok && useApiHealthStore.getState().wake.open) {
      useApiHealthStore.getState().markHealthResult(true);
    }
  };
}
