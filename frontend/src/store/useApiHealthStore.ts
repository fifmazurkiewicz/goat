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
 * Stan okna wybudzania Rendera (ADR-19). Sonda HTTP żyje w `useApiHealthProbe`;
 * `apiFetch` woła `startWakeWindow({ force: true })` przy błędzie sieci.
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

/** Błąd sieci w prawdziwym requeście — nowe okno wybudzania, nie 4xx/Abort. */
export function reportApiNetworkError(err: unknown): void {
  if (isNetworkError(err)) {
    useApiHealthStore.getState().startWakeWindow({ force: true });
  }
}

/**
 * Jeśli prawdziwy request wisi ≥ 2 s, otwiera okno wybudzania (cold start po bezczynności).
 * Wywołaj zwracany `finish(ok)` po zakończeniu fetcha — przy sukcesie gasi lampkę.
 */
export function watchSlowApiRequest(): (ok: boolean) => void {
  const timeoutId = window.setTimeout(() => {
    useApiHealthStore.getState().startWakeWindow({ force: true });
  }, API_HEALTH_WAKING_AFTER_MS);

  return (ok: boolean) => {
    window.clearTimeout(timeoutId);
    if (ok && useApiHealthStore.getState().wake.open) {
      useApiHealthStore.getState().markHealthResult(true);
    }
  };
}
