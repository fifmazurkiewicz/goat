import { useState } from "react";
import { toast } from "sonner";

import { ResponsiveDialog } from "@/components/common/ResponsiveDialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useClonePersona, useCommunityPersonas } from "@/hooks/usePersonas";
import { ApiError } from "@/lib/api-client";
import { PERSONA_TYPE_LABELS } from "@/lib/persona-labels";
import type { Persona } from "@/types/api";

interface CommunitySectionProps {
  isAtLimit: boolean;
  maxActivePersonas: number;
}

/**
 * "Przeglądaj community" (docs/technical/database-schema.md — personas.is_shared,
 * RLS SELECT gdy is_shared=true AND moderation_status='approved'). Klonowanie tworzy
 * nowy rekord z user_id usera; jeśli konto jest na limicie, informujemy o tym PRZED
 * próbą klonowania (żeby błąd 409 nie był zaskoczeniem).
 */
export function CommunitySection({ isAtLimit, maxActivePersonas }: CommunitySectionProps) {
  const { data: community, isLoading } = useCommunityPersonas();
  const clonePersona = useClonePersona();
  const [previewPersona, setPreviewPersona] = useState<Persona | null>(null);

  async function handleClone(persona: Persona) {
    try {
      await clonePersona.mutateAsync(persona.id);
      toast.success(`Sklonowano „${persona.name}” do Twoich person`);
      setPreviewPersona(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nie udało się sklonować persony.");
    }
  }

  return (
    <section className="mt-10">
      <div className="mb-4 h-px bg-border" />
      <h2 className="text-xl font-semibold">Przeglądaj community</h2>
      <p className="mt-1 max-w-[70ch] text-sm text-muted-foreground">
        Persony, które udostępnili inni użytkownicy — sklonuj do swoich w jednym kliknięciu.
      </p>
      {isAtLimit ? (
        <p className="mt-2 text-sm text-amber-600 dark:text-amber-500">
          Masz już {maxActivePersonas}/{maxActivePersonas} aktywnych person — sklonowanie zajmie wolne miejsce
          dopiero po dezaktywacji którejś z obecnych.
        </p>
      ) : null}

      {isLoading ? (
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {(community ?? []).map((persona) => (
            <Card key={persona.id} className="flex flex-col gap-2 p-4">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {PERSONA_TYPE_LABELS[persona.type]}
              </div>
              <div className="text-base font-semibold">{persona.name}</div>
              <p className="line-clamp-2 text-sm text-muted-foreground">{persona.system_prompt}</p>
              <div className="mt-1 flex gap-2">
                <Button type="button" variant="ghost" size="sm" className="px-0" onClick={() => setPreviewPersona(persona)}>
                  Podgląd promptu →
                </Button>
              </div>
              <Button
                type="button"
                variant="secondary"
                className="mt-auto"
                onClick={() => handleClone(persona)}
                disabled={clonePersona.isPending}
              >
                Sklonuj do swoich
              </Button>
            </Card>
          ))}
          {(community ?? []).length === 0 ? (
            <p className="col-span-full text-sm text-muted-foreground">
              Nikt jeszcze nie udostępnił żadnej persony.
            </p>
          ) : null}
        </div>
      )}

      <ResponsiveDialog
        open={Boolean(previewPersona)}
        onOpenChange={(open) => !open && setPreviewPersona(null)}
        title={previewPersona?.name ?? ""}
        description={previewPersona ? PERSONA_TYPE_LABELS[previewPersona.type] : undefined}
        footer={
          <>
            <Button variant="secondary" onClick={() => setPreviewPersona(null)}>
              Zamknij
            </Button>
            {previewPersona ? (
              <Button onClick={() => handleClone(previewPersona)} disabled={clonePersona.isPending}>
                Sklonuj do swoich
              </Button>
            ) : null}
          </>
        }
      >
        <p className="whitespace-pre-line text-sm">{previewPersona?.system_prompt}</p>
      </ResponsiveDialog>
    </section>
  );
}
