import type { PropsWithChildren } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuthStore } from "@/store/useAuthStore";

/**
 * Guard "zalogowany" dla tras chronionych (docs/technical/frontend.md #1).
 * Czeka na inicjalizację sesji (OAuth PKCE / getSession / dev auth), żeby nie wyrzucać
 * na /login w momencie gdy token jest właśnie wymieniany po powrocie z Google.
 */
export function ProtectedRoute({ children }: PropsWithChildren) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const isInitialized = useAuthStore((state) => state.isInitialized);
  const location = useLocation();

  if (!isInitialized) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Ładowanie…
      </div>
    );
  }

  if (!isAuthenticated) {
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
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const isAdmin = useAuthStore((state) => state.isAdmin);
  const isInitialized = useAuthStore((state) => state.isInitialized);
  const location = useLocation();

  if (!isInitialized) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Ładowanie…
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (!isAdmin) {
    return <Navigate to="/personas" replace />;
  }

  return <>{children}</>;
}
