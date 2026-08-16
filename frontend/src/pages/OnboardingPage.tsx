import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Pierwszy ekran po zalogowaniu — galeria 6 szablonów person
 * (docs/technical/frontend.md sekcja 1, persona_templates w
 * database-schema.md). TODO: fetch `persona_templates` przez TanStack Query,
 * karty do wyboru + akcja "utwórz z szablonu" → POST /personas.
 *
 * Dane biometryczne (waga/wzrost/cel — `user_profile`, ADR-11) NIE są zbierane tutaj
 * formularzem — persona dopytuje o nie naturalnie w pierwszej rozmowie na `/chat`
 * (patrz docs/technical/ai-pipeline.md sekcja 0). `/profile` istnieje jako fallback dla
 * userów wolących wypełnić dane wprost.
 */
export default function OnboardingPage() {
  return (
    <div className="container py-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] md:py-10">
      <Card>
        <CardHeader>
          <CardTitle>Onboarding</CardTitle>
          <CardDescription>
            Tu pojawi się galeria 6 szablonów person (trener personalny, dietetyk, psycholog
            sportowy, psycholog, trener motoryczny, trener badmintona) do wyboru jako pierwszy krok.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">TODO: kolejny etap.</CardContent>
      </Card>
    </div>
  );
}
