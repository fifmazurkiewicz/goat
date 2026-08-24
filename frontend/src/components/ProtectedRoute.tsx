import type { PropsWithChildren } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuthStore } from "@/store/useAuthStore";

/**
 * "Authenticated" guard for protected routes (docs/technical/frontend.md #1).
 * Waits for session initialization (OAuth PKCE / getSession / dev auth) so the user
 * is not bounced to /login at the exact moment the token is being exchanged after the
 * return from Google.
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
 * "Authenticated + admin" guard for /admin — the `is_admin` check on the UI side is
 * only a convenience; the backend re-verifies it explicitly in code
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
