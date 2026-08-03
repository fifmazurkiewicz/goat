import { Separator } from "@/components/ui/separator";
import { AccountSettingsCard } from "@/components/settings/AccountSettingsCard";
import { ExerciseCatalog } from "@/components/settings/ExerciseCatalog";

/**
 * `/settings` (NOWA, ADR-15) — konto (nick, motyw) + katalog ćwiczeń (ADR-14).
 * docs/technical/frontend.md sekcja 7a.
 */
export default function SettingsPage() {
  return (
    <div className="container max-w-4xl py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Ustawienia</h1>
      <p className="mt-2 max-w-[60ch] text-muted-foreground">Twój nick, wygląd aplikacji i katalog ćwiczeń.</p>

      <div className="mt-6">
        <AccountSettingsCard />
      </div>

      <Separator className="my-10" />

      <ExerciseCatalog />
    </div>
  );
}
