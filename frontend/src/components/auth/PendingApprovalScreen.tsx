import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

/**
 * Waiting room for authenticated but unapproved accounts (ADR-22).
 * Trust-first product screen: VARIANCE 3 / MOTION 2 / DENSITY 5. Goat tokens only.
 */
export function PendingApprovalScreen({
  onCheckStatus,
  onLogout,
  isChecking,
}: {
  onCheckStatus: () => void;
  onLogout: () => void;
  isChecking: boolean;
}) {
  return (
    <div className="flex min-h-dvh items-start justify-center bg-background p-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-[max(2rem,env(safe-area-inset-top))] sm:items-center">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Konto oczekuje na akceptację</CardTitle>
          <CardDescription>
            Twoje konto jest już utworzone. Dostęp do Coach otworzy się, gdy administrator je zaakceptuje.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <Button type="button" className="min-h-11 w-full" onClick={onCheckStatus} disabled={isChecking}>
            {isChecking ? "Sprawdzanie…" : "Sprawdź status"}
          </Button>
          <Button type="button" variant="outline" className="min-h-11 w-full" onClick={onLogout}>
            Wyloguj
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
