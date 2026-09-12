import { useState, type PropsWithChildren } from "react";
import { Link, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useGrantPrivacyConsent, usePrivacyConsent } from "@/hooks/usePrivacy";
import { getErrorMessage } from "@/lib/api-client";

export function PrivacyConsentGate({ children }: PropsWithChildren) {
  const { data, isPending, isError, refetch } = usePrivacyConsent();
  const grant = useGrantPrivacyConsent();
  const [confirmed, setConfirmed] = useState(false);
  const [aiConfirmed, setAiConfirmed] = useState(false);
  const location = useLocation();
  const sensitivePath = ["/chat", "/plans", "/results", "/profile"].some(
    (path) => location.pathname === path || location.pathname.startsWith(`${path}/`)
  );

  // Non-sensitive areas must never wait for the consent API.
  if (!sensitivePath) return children;
  if (isPending) return <div className="flex min-h-dvh items-center justify-center text-sm text-muted-foreground">Sprawdzanie zgód…</div>;
  if (data?.health_data.active) return children;

  return (
    <div className="flex min-h-dvh items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>Zgoda na przetwarzanie danych zdrowotnych</CardTitle>
          <CardDescription>
            Goat potrzebuje tych danych, aby personalizować rozmowy, wyniki i plany. Odpowiedzi tworzy AI i mogą zawierać błędy; aplikacja nie zastępuje lekarza.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p>Dane profilu, wiadomości i wyniki mogą ujawniać informacje o zdrowiu. Są przetwarzane przez Goat i dostawców infrastruktury opisanych w <Link className="underline" to="/privacy">Polityce prywatności</Link>.</p>
          <label className="flex items-start gap-3 rounded-md border p-3">
            <input className="mt-1" type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
            <span>Wyrażam dobrowolną, wyraźną zgodę na przetwarzanie moich danych dotyczących zdrowia w celu świadczenia spersonalizowanych funkcji coachingowych.</span>
          </label>
          <label className="flex items-start gap-3 rounded-md border p-3">
            <input className="mt-1" type="checkbox" checked={aiConfirmed} onChange={(event) => setAiConfirmed(event.target.checked)} />
            <span>Rozumiem, że rozmawiam z systemem AI, którego odpowiedzi i plany mogą zawierać błędy i nie zastępują porady medycznej.</span>
          </label>
          <p className="text-muted-foreground">Zgodę możesz wycofać w Ustawieniach. Po wycofaniu czat, profil, wyniki i generowanie planów przestaną działać do czasu ponownego udzielenia zgody.</p>
          {isError || grant.isError ? <p className="text-destructive">{getErrorMessage(grant.error, "Nie udało się sprawdzić lub zapisać zgody.")}</p> : null}
          <div className="flex flex-wrap gap-2">
            <Button disabled={!confirmed || !aiConfirmed || grant.isPending} onClick={() => void grant.mutateAsync()}>{grant.isPending ? "Zapisywanie…" : "Wyrażam zgodę i przechodzę dalej"}</Button>
            {isError ? <Button variant="outline" onClick={() => void refetch()}>Spróbuj ponownie</Button> : null}
            <Button asChild variant="outline"><Link to="/settings">Ustawienia prywatności</Link></Button>
            <Button asChild variant="ghost"><Link to="/personas">Wróć do person</Link></Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
