import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiStatusLamp } from "@/components/layout/ApiStatusLamp";
import { getErrorMessage } from "@/lib/api-client";
import { isDevLoginEnabled, signInWithDevCredentials } from "@/lib/dev-auth";
import { signInWithGoogle } from "@/lib/supabase";
import { useApiHealthStore } from "@/store/useApiHealthStore";
import { useAuthStore } from "@/store/useAuthStore";

/**
 * Public login page.
 * Locally (`VITE_ENABLE_DEV_LOGIN=true`): email/password through backend.
 * Production: Google OAuth via Supabase Auth only (ADR-5).
 */
export default function LoginPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const isInitialized = useAuthStore((state) => state.isInitialized);
  const setDevAuth = useAuthStore((state) => state.setDevAuth);
  const lamp = useApiHealthStore((state) => state.lamp);
  const startWakeWindow = useApiHealthStore((state) => state.startWakeWindow);
  const location = useLocation();
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isInitialized) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-sm text-muted-foreground">
        Ładowanie…
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to={from && from !== "/login" ? from : "/personas"} replace />;
  }

  async function handleDevLogin(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    startWakeWindow({ force: true });
    try {
      const devAuth = await signInWithDevCredentials(email, password);
      setDevAuth(devAuth);
    } catch (err) {
      setError(getErrorMessage(err, "Nie udało się zalogować."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-start justify-center bg-background p-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-[max(2rem,env(safe-area-inset-top))] sm:items-center">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="flex items-center justify-center gap-1">
            goat
            <ApiStatusLamp lamp={lamp} onRetry={() => startWakeWindow({ force: true })} />
          </CardTitle>
          <CardDescription>Twój wielo-personowy asystent treningowy i dietetyczny.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isDevLoginEnabled ? (
            <form className="space-y-4" onSubmit={(event) => void handleDevLogin(event)}>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Hasło</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </div>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <Button className="w-full" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Logowanie…" : "Zaloguj się"}
              </Button>
            </form>
          ) : (
            <Button className="w-full" onClick={() => void signInWithGoogle()}>
              Zaloguj się przez Google
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
