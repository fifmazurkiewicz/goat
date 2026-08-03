import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";

/**
 * Czyta globalny `usePlanGenerationStore` (mountowany + pollowany w AppShell przez
 * `usePlanGenerationPolling`), NIE robi własnego pollingu — docs/technical/frontend.md
 * sekcja 5.
 */
export function PlanGenerationBanner() {
  const status = usePlanGenerationStore((state) => state.status);
  const breakdown = usePlanGenerationStore((state) => state.breakdown);

  if (status === "idle" || status === "ready") return null;

  if (status === "generating") {
    return (
      <Alert className="mb-4">
        <AlertTitle>Generowanie planu w toku…</AlertTitle>
        <AlertDescription>To może potrwać do kilku minut — możesz spokojnie zamknąć tę stronę.</AlertDescription>
      </Alert>
    );
  }

  if (status === "partial_ready") {
    const failed = breakdown.filter((b) => b.status === "failed");
    return (
      <Alert variant="warning" className="mb-4">
        <AlertTitle>Plan częściowo gotowy</AlertTitle>
        <AlertDescription>
          {failed.length > 0
            ? `Nie udało się wygenerować planu dla ${failed.length} person(y). Spróbuj wygenerować plan ponownie.`
            : "Część planu wymaga ponownego wygenerowania."}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Alert variant="destructive" className="mb-4">
      <AlertTitle>Generowanie planu nie powiodło się</AlertTitle>
      <AlertDescription>Spróbuj wygenerować plan ponownie.</AlertDescription>
    </Alert>
  );
}
