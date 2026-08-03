import type { PropsWithChildren } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuthStore } from "@/store/useAuthStore";

/**
 * Guard "zalogowany" dla tras chronionych (docs/technical/frontend.md #1).
 * Guard "min. 1 aktywna persona" na /chat i /plans jest świadomie odłożony
 * (ADR-8) — dodać dopiero jako loader route'u, nie tutaj, żeby uniknąć
 * duplikowania fetcha z `usePersonaStore`.
 */
export function ProtectedRoute({ children }: PropsWithChildren) {
  const session = useAuthStore((state) => state.session);
  const location = useLocation();

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}

/**
 * Guard "zalogowany + admin" dla /admin — weryfikacja `is_admin` po stronie
 * UI jest tylko wygodą, backend i tak weryfikuje jawnie w kodzie
 * (docs/technical/architecture.md #2, #8).
 */
export function AdminRoute({ children }: PropsWithChildren) {
  const session = useAuthStore((state) => state.session);
  const isAdmin = useAuthStore((state) => state.isAdmin);
  const location = useLocation();

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (!isAdmin) {
    return <Navigate to="/personas" replace />;
  }

  return <>{children}</>;
}
