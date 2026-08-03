import { Navigate, useLocation } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { signInWithGoogle } from "@/lib/supabase";
import { useAuthStore } from "@/store/useAuthStore";

/**
 * Publiczna strona logowania — wyłącznie Google OAuth przez Supabase Auth,
 * bez magic linka (ADR-5). Po zalogowaniu Supabase wraca pod `/personas`;
 * `onAuthStateChange` (App.tsx) zapisuje sesję w `useAuthStore`.
 */
export default function LoginPage() {
  const session = useAuthStore((state) => state.session);
  const isInitialized = useAuthStore((state) => state.isInitialized);
  const location = useLocation();
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;

  if (!isInitialized) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Ładowanie…
      </div>
    );
  }

  if (session) {
    return <Navigate to={from && from !== "/login" ? from : "/personas"} replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle>goat</CardTitle>
          <CardDescription>Twój wielo-personowy asystent treningowy i dietetyczny.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button className="w-full" onClick={() => void signInWithGoogle()}>
            Zaloguj się przez Google
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
