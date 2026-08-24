import { useEffect } from "react";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { AdminRoute, ProtectedRoute } from "@/components/ProtectedRoute";
import { AppShell } from "@/components/layout/AppShell";
import { Toaster } from "@/components/ui/sonner";
import { useApiHealthProbe } from "@/hooks/useApiHealthProbe";
import { isDevLoginEnabled, loadDevAuth } from "@/lib/dev-auth";
import { supabase } from "@/lib/supabase";
import { useAuthStore } from "@/store/useAuthStore";

import AdminPage from "@/pages/AdminPage";
import ChatPage from "@/pages/ChatPage";
import ExerciseDetailPage from "@/pages/ExerciseDetailPage";
import LoginPage from "@/pages/LoginPage";
import OnboardingPage from "@/pages/OnboardingPage";
import PersonasPage from "@/pages/PersonasPage";
import PlansPage from "@/pages/PlansPage";
import ProfilePage from "@/pages/ProfilePage";
import ResultsPage from "@/pages/ResultsPage";
import SettingsPage from "@/pages/SettingsPage";

/**
 * Routing per docs/technical/frontend.md section 1. "Min. 1 active persona" guard on
 * /chat and /plans — intentionally deferred (ADR-8).
 */
const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/personas" replace /> },
  { path: "/login", element: <LoginPage /> },
  {
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      { path: "/onboarding", element: <OnboardingPage /> },
      { path: "/personas", element: <PersonasPage /> },
      { path: "/chat", element: <ChatPage /> },
      { path: "/chat/:sessionId", element: <ChatPage /> },
      { path: "/plans", element: <PlansPage /> },
      { path: "/exercises/:slug", element: <ExerciseDetailPage /> },
      { path: "/results", element: <ResultsPage /> },
      { path: "/profile", element: <ProfilePage /> },
      { path: "/settings", element: <SettingsPage /> },
      {
        path: "/admin",
        element: (
          <AdminRoute>
            <AdminPage />
          </AdminRoute>
        ),
      },
    ],
  },
]);

export default function App() {
  const setSession = useAuthStore((state) => state.setSession);
  const setDevAuth = useAuthStore((state) => state.setDevAuth);
  const setInitialized = useAuthStore((state) => state.setInitialized);

  useApiHealthProbe();

  useEffect(() => {
    let active = true;

    if (isDevLoginEnabled) {
      const saved = loadDevAuth();
      if (saved) setDevAuth(saved);
      setInitialized();
      return () => {
        active = false;
      };
    }

    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      setInitialized();
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setInitialized();
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, [setSession, setDevAuth, setInitialized]);

  return (
    <>
      <RouterProvider router={router} />
      <Toaster />
    </>
  );
}
