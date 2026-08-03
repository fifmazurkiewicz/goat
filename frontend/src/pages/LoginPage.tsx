import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { signInWithGoogle } from "@/lib/supabase";

/**
 * Publiczna strona logowania — wyłącznie Google OAuth przez Supabase Auth,
 * bez magic linka (ADR-5). Po zalogowaniu Supabase przekierowuje z powrotem
 * pod `window.location.origin`; `onAuthStateChange` (podpięty w App.tsx)
 * zapisuje sesję w `useAuthStore`.
 */
export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle>Coach</CardTitle>
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
