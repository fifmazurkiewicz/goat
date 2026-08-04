import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useCancelPlanJob } from "@/hooks/usePlans";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";

function planGenerationProgress(breakdown: { status: string }[]): number | null {
  if (breakdown.length === 0) return null;
  const done = breakdown.filter((p) => p.status === "done" || p.status === "failed").length;
  return Math.round((done / breakdown.length) * 100);
}

/**
 * Czyta globalny `usePlanGenerationStore` (mountowany + pollowany w AppShell przez
 * `usePlanGenerationPolling`), NIE robi własnego pollingu — docs/technical/frontend.md
 * sekcja 5.
 */
export function PlanGenerationBanner() {
  const status = usePlanGenerationStore((state) => state.status);
  const jobId = usePlanGenerationStore((state) => state.jobId);
  const breakdown = usePlanGenerationStore((state) => state.breakdown);
  const reset = usePlanGenerationStore((state) => state.reset);
  const cancelJob = useCancelPlanJob();

  if (status === "idle" || status === "ready") return null;

  async function handleCancel() {
    if (!jobId) {
      reset();
      return;
    }
    try {
      await cancelJob.mutateAsync(jobId);
      reset();
      toast.info("Anulowano generowanie planu.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Nie udało się anulować generowania.");
    }
  }

  if (status === "generating") {
    const progress = planGenerationProgress(breakdown);
    const doneCount = breakdown.filter((p) => p.status === "done").length;
    const failedCount = breakdown.filter((p) => p.status === "failed").length;

    return (
      <Alert className="mb-4">
        <AlertTitle className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Generowanie planu w toku…
        </AlertTitle>
        <AlertDescription className="space-y-3">
          <p>To może potrwać kilka minut — każda persona zapisuje swój fragment osobno; możesz śledzić postęp poniżej.</p>
          {progress !== null ? (
            <div className="space-y-1">
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${Math.max(progress, 8)}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Postęp person: {doneCount}/{breakdown.length}
                {failedCount > 0 ? ` (${failedCount} nieudanych)` : ""}
              </p>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Przygotowywanie joba…</p>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={cancelJob.isPending}
            onClick={() => void handleCancel()}
          >
            Anuluj generowanie
          </Button>
        </AlertDescription>
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
