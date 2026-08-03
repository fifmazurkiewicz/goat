import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useGeneratePlan } from "@/hooks/usePlans";
import { ApiError } from "@/lib/api-client";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";

interface GeneratePlanCtaProps {
  startDate: string;
}

export function GeneratePlanCta({ startDate }: GeneratePlanCtaProps) {
  const generatePlan = useGeneratePlan();
  const status = usePlanGenerationStore((state) => state.status);
  const isGenerating = status === "generating";

  async function handleGenerate(periodType: "week" | "month") {
    try {
      await generatePlan.mutateAsync({ period_type: periodType, start_date: startDate });
      toast.info("Rozpoczęto generowanie planu — to może potrwać do kilku minut.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nie udało się rozpocząć generowania planu.");
    }
  }

  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle>Brak planu na ten okres</CardTitle>
        <CardDescription>
          Wygeneruj wspólny plan wszystkich aktywnych person — trening, dieta i regeneracja zsynchronizowane
          na cały tydzień lub miesiąc.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex gap-2">
        <Button type="button" onClick={() => handleGenerate("week")} disabled={isGenerating || generatePlan.isPending}>
          Wygeneruj plan tygodnia
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => handleGenerate("month")}
          disabled={isGenerating || generatePlan.isPending}
        >
          Wygeneruj plan miesiąca
        </Button>
      </CardContent>
    </Card>
  );
}
