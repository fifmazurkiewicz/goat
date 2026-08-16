import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { API_BASE_URL } from "@/lib/api-client";
import {
  API_HEALTH_ATTEMPT_TIMEOUT_MS,
  API_HEALTH_DOWN_AFTER_MS,
  shouldProbeHealth,
} from "@/lib/api-health";
import { useApiHealthStore } from "@/store/useApiHealthStore";

const TICK_MS = 250;

function isTabVisible(): boolean {
  return document.visibilityState === "visible";
}

/**
 * Sonda `/api/health` wyłącznie w otwartym oknie wybudzania (ADR-19).
 * Montować w `App` — samo `/login` nie otwiera okna.
 */
export function useApiHealthProbe() {
  const queryClient = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function probe() {
      const { wake, markProbeStarted, markHealthResult } = useApiHealthStore.getState();
      const now = Date.now();
      if (!shouldProbeHealth(wake, now, isTabVisible()) || !API_BASE_URL) return;

      markProbeStarted();
      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutId = window.setTimeout(() => controller.abort(), API_HEALTH_ATTEMPT_TIMEOUT_MS);

      try {
        const res = await fetch(`${API_BASE_URL}/api/health`, {
          method: "GET",
          signal: controller.signal,
        });
        if (cancelled) return;
        const ok = res.ok;
        markHealthResult(ok);
      } catch {
        if (cancelled) return;
        if (!useApiHealthStore.getState().wake.open) return;
        markHealthResult(false);
      } finally {
        window.clearTimeout(timeoutId);
        if (abortRef.current === controller) abortRef.current = null;
      }
    }

    function onVisibility() {
      if (isTabVisible()) return;
      abortRef.current?.abort();
      abortRef.current = null;
      useApiHealthStore.getState().closeWakeWindow();
    }

    const unsub = useApiHealthStore.subscribe((state, prev) => {
      if (!state.wake.open && prev.wake.open) {
        abortRef.current?.abort();
      }
      if (state.wake.succeeded && !prev.wake.succeeded) {
        void queryClient.invalidateQueries();
      }
      void probe();
    });

    const tickId = window.setInterval(() => {
      const { wake, tick, markHealthResult } = useApiHealthStore.getState();
      if (!wake.open) return;
      const now = Date.now();
      tick(now);
      if (wake.startedAt !== null && now - wake.startedAt >= API_HEALTH_DOWN_AFTER_MS) {
        abortRef.current?.abort();
        if (wake.inFlight) markHealthResult(false);
      }
      void probe();
    }, TICK_MS);

    document.addEventListener("visibilitychange", onVisibility);
    void probe();

    return () => {
      cancelled = true;
      unsub();
      window.clearInterval(tickId);
      document.removeEventListener("visibilitychange", onVisibility);
      abortRef.current?.abort();
    };
  }, [queryClient]);
}
