import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * First screen after login — gallery of 6 persona templates
 * (docs/technical/frontend.md section 1, persona_templates in
 * database-schema.md). TODO: fetch `persona_templates` via TanStack Query,
 * selectable cards + "create from template" action → POST /personas.
 *
 * Biometric data (weight/height/goal — `user_profile`, ADR-11) is NOT collected here
 * via a form — the persona asks for it naturally during the first conversation on `/chat`
 * (see docs/technical/ai-pipeline.md section 0). `/profile` exists as a fallback for
 * users who prefer to fill in the data directly.
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
