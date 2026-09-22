import { Loader2, X } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useCancelPlanJob } from "@/hooks/usePlans";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";

const PHASE_LABELS = {
  preparing: "Przygotowywanie planu",
  coordinating: "Goat układa wspólny szkic",
  generating_personas: "Persony przygotowują swoje części",
  harmonizing: "Goat uzgadnia finalny plan",
  finished: "Plan gotowy",
} as const;

/** Compact, app-wide status so generation remains visible outside the Plans screen. */
export function PlanGenerationStatus() {
  const status = usePlanGenerationStore((state) => state.status);
  const jobId = usePlanGenerationStore((state) => state.jobId);
  const phase = usePlanGenerationStore((state) => state.phase);
  const breakdown = usePlanGenerationStore((state) => state.breakdown);
  const reset = usePlanGenerationStore((state) => state.reset);
  const cancelJob = useCancelPlanJob();

  if (status !== "generating") return null;

  const completed = breakdown.filter((persona) => persona.status === "done" || persona.status === "failed").length;
  const progress = breakdown.length ? ` · ${completed}/${breakdown.length}` : "";

  async function cancel() {
    if (!jobId) return;
    try {
      await cancelJob.mutateAsync(jobId);
      reset();
      toast.info("Anulowano generowanie planu.");
    } catch {
      toast.error("Nie udało się anulować generowania planu.");
    }
  }

  return (
    <div className="border-b bg-muted/40 px-3 py-1.5 sm:px-4">
      <div className="mx-auto flex max-w-5xl items-center gap-2 text-xs sm:text-sm">
        <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden="true" />
        <span className="min-w-0 flex-1 truncate">
          {phase ? PHASE_LABELS[phase] : "Generowanie planu"}{progress}
        </span>
        <Link to="/plans" className="shrink-0 font-medium underline underline-offset-2">
          Zobacz plan
        </Link>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          disabled={cancelJob.isPending}
          onClick={() => void cancel()}
          aria-label="Anuluj generowanie planu"
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
