import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Wykresy trendu per kategoria/metryka (`recharts` przez shadcn `Chart`,
 * docs/technical/frontend.md sekcja 6, dane z GET /results?category=&metric=).
 * TODO: kolejny etap.
 */
export default function ResultsPage() {
  return (
    <div className="container py-10">
      <Card>
        <CardHeader>
          <CardTitle>Wyniki</CardTitle>
          <CardDescription>
            Tu pojawią się wykresy trendu (waga, ciężary, czasy biegowe) filtrowane po kategorii i
            metryce.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">TODO: kolejny etap.</CardContent>
      </Card>
    </div>
  );
}
