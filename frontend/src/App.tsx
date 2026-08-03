import { useEffect } from "react";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { AdminRoute, ProtectedRoute } from "@/components/ProtectedRoute";
import { AppShell } from "@/components/layout/AppShell";
import { Toaster } from "@/components/ui/sonner";
import { supabase } from "@/lib/supabase";
import { useAuthStore } from "@/store/useAuthStore";

import AdminPage from "@/pages/AdminPage";
import ChatPage from "@/pages/ChatPage";
import LoginPage from "@/pages/LoginPage";
import OnboardingPage from "@/pages/OnboardingPage";
import PersonasPage from "@/pages/PersonasPage";
import PlansPage from "@/pages/PlansPage";
import ResultsPage from "@/pages/ResultsPage";
import SettingsPage from "@/pages/SettingsPage";

/**
 * Routing zgodny z docs/technical/frontend.md sekcja 1. Guard "min. 1
 * aktywna persona" na /chat i /plans — świadomie odłożony (ADR-8).
 * `/profile` usunięte z nav — biometria przez czat (`update_user_profile`).
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
      { path: "/results", element: <ResultsPage /> },
      { path: "/profile", element: <Navigate to="/settings" replace /> },
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
  const setInitialized = useAuthStore((state) => state.setInitialized);

  useEffect(() => {
    let active = true;

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
  }, [setSession, setInitialized]);

  return (
    <>
      <RouterProvider router={router} />
      <Toaster />
    </>
  );
}
