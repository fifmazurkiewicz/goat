import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Docelowa struktura (docs/technical/frontend.md sekcja 5):
 * CalendarViewSwitcher (Week/Month wg breakpointu) + DayPanel (Sheet,
 * responsywny side) + PlanGenerationBanner czytający globalny
 * `usePlanGenerationStore` (bez własnego pollingu). TODO: kolejny etap.
 */
export default function PlansPage() {
  return (
    <div className="container py-10">
      <Card>
        <CardHeader>
          <CardTitle>Plany</CardTitle>
          <CardDescription>
            Tu pojawi się kalendarz planu (widok tygodniowy na mobile, miesięczny na desktopie) z
            panelem dnia pokazującym "Zaplanowane" i "Zrealizowane".
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">TODO: kolejny etap.</CardContent>
      </Card>
    </div>
  );
}
