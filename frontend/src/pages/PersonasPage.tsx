import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Lista person usera + akcje create/edit/clone/share (docs/technical/
 * database-schema.md — personas). TODO: formularz edycji persony (React Hook
 * Form + Zod) opisany w docs/technical/frontend.md sekcja 7 — kolejny etap.
 *
 * Limit aktywnych person jest PER KONTO (domyślnie 5, edytowalny przez admina —
 * ADR-12), nie sztywną globalną liczbą — komunikat przy osiągnięciu limitu powinien
 * pokazywać aktualną wartość z odpowiedzi błędu backendu, nie hardkodowane "5".
 */
export default function PersonasPage() {
  return (
    <div className="container py-10">
      <Card>
        <CardHeader>
          <CardTitle>Persony</CardTitle>
          <CardDescription>
            Tu pojawi się lista Twoich person (limit aktywnych ustalony przez admina, domyślnie
            5) z akcjami tworzenia, edycji, klonowania i udostępniania.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">TODO: kolejny etap.</CardContent>
      </Card>
    </div>
  );
}
