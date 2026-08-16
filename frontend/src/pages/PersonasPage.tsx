import { useState } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { CommunitySection } from "@/components/personas/CommunitySection";
import { PersonaCard } from "@/components/personas/PersonaCard";
import { PersonaConfigDialog } from "@/components/personas/PersonaConfigDialog";
import { PersonaFormDialog } from "@/components/personas/PersonaFormDialog";
import { usePersonas } from "@/hooks/usePersonas";
import { PAGE_SHELL_CLASS, PAGE_TITLE_CLASS } from "@/lib/layout";
import type { Persona } from "@/types/api";

/**
 * Siatka person usera (limit z `profiles.max_active_personas`, ADR-12 — NIE hardkodowane
 * "5") + karta-placeholder "wolne miejsce" + community (docs/technical/frontend.md
 * sekcja 7, sekcja 11 dla mobile).
 */
export default function PersonasPage() {
  const { data, isLoading } = usePersonas();
  const [formPersona, setFormPersona] = useState<Persona | undefined>(undefined);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [configPersona, setConfigPersona] = useState<Persona | null>(null);

  const personas = data?.items ?? [];
  const maxActivePersonas = data?.max_active_personas ?? 5;
  const activeCount = personas.filter((p) => p.active).length;
  const isAtLimit = activeCount >= maxActivePersonas;
  const freeSlots = Math.max(maxActivePersonas - personas.length, 0);

  function openCreateDialog() {
    setFormPersona(undefined);
    setIsFormOpen(true);
  }

  function openEditDialog(persona: Persona) {
    setConfigPersona(null);
    setFormPersona(persona);
    setIsFormOpen(true);
  }

  return (
    <div className={PAGE_SHELL_CLASS}>
      <h1 className={PAGE_TITLE_CLASS}>Twoi trenerzy</h1>
      <p className="mt-2 max-w-[70ch] text-muted-foreground">
        Do {maxActivePersonas} person, każda ze swoim głosem i celem. Włącz, edytuj prompt albo zajrzyj do person,
        które udostępnili inni.
      </p>

      {isLoading ? (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-64 w-full" />
          ))}
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {personas.map((persona) => (
            <PersonaCard
              key={persona.id}
              persona={persona}
              onOpenConfig={setConfigPersona}
              onEdit={openEditDialog}
            />
          ))}
          {freeSlots > 0 ? (
            <Card className="flex min-h-[220px] items-center justify-center border-dashed p-4">
              <div className="text-center">
                <div className="mb-2 text-base font-semibold">
                  {freeSlots === 1 ? "Ostatnie wolne miejsce" : `${freeSlots} wolnych miejsc`}
                </div>
                <CardContent className="p-0 pb-3 text-sm text-muted-foreground">
                  Psycholog, trener siłowy, dietetyk — dobierz kogoś, kto Ci brakuje.
                </CardContent>
                <Button type="button" onClick={openCreateDialog}>
                  <Plus className="mr-1 h-4 w-4" /> Dodaj personę
                </Button>
              </div>
            </Card>
          ) : null}
        </div>
      )}

      {personas.length === 0 && !isLoading && freeSlots === 0 ? (
        <p className="mt-6 text-sm text-muted-foreground">
          Limit aktywnych person ustawiony przez administratora wynosi 0 — skontaktuj się z administratorem.
        </p>
      ) : null}

      <CommunitySection isAtLimit={isAtLimit} maxActivePersonas={maxActivePersonas} />

      <PersonaFormDialog open={isFormOpen} onOpenChange={setIsFormOpen} persona={formPersona} />
      <PersonaConfigDialog
        persona={configPersona}
        onOpenChange={(open) => !open && setConfigPersona(null)}
        onEdit={openEditDialog}
      />
    </div>
  );
}
