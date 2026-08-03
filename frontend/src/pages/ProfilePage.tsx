import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Formularz-FALLBACK dla `user_profile` (waga/wzrost/wiek/poziom aktywności/cel) —
 * ścieżka alternatywna do głównej, konwersacyjnej: dowolna persona dopytuje o te dane
 * naturalnie w czacie i zapisuje je narzędziem `update_user_profile` (patrz
 * docs/technical/ai-pipeline.md sekcja 0, ADR-11). Ten ekran jest dla userów wolących
 * wypełnić dane wprost zamiast o nich rozmawiać — obie ścieżki piszą do tej samej tabeli.
 *
 * TODO kolejny etap: `GET/PATCH /api/v1/profile` przez TanStack Query, formularz
 * (React Hook Form + Zod) z polami height_cm/weight_kg/date_of_birth/sex/activity_level/
 * primary_goal/notes — walidacja zakresów zgodna z `UserProfileUpdate` w backendzie.
 */
export default function ProfilePage() {
  return (
    <div className="container py-10">
      <Card>
        <CardHeader>
          <CardTitle>Twój profil</CardTitle>
          <CardDescription>
            Waga, wzrost, wiek, poziom aktywności i cel — dane, na których persony opierają
            personalizację treningu i diety. Możesz je podać tutaj albo po prostu odpowiedzieć,
            gdy persona zapyta o nie w czacie.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">TODO: kolejny etap.</CardContent>
      </Card>
    </div>
  );
}
