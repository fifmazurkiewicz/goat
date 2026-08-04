import { useState } from "react";
import { toast } from "sonner";

import { ResponsiveDialog } from "@/components/common/ResponsiveDialog";
import { Button } from "@/components/ui/button";
import { useCreateChatSession } from "@/hooks/useChatSessions";
import { getErrorMessage } from "@/lib/api-client";
import { PERSONA_TYPE_LABELS } from "@/lib/persona-labels";
import { cn } from "@/lib/utils";
import type { Persona } from "@/types/api";

interface NewSessionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  personas: Persona[];
  onCreated: (sessionId: string) => void;
}

/**
 * §4a — "+ Nowa rozmowa" otwiera krótki wybór: "Ogólna rozmowa" (auto-routing,
 * `persona_id: null`) vs wybór konkretnej persony z listy aktywnych (1:1).
 */
export function NewSessionDialog({ open, onOpenChange, personas, onCreated }: NewSessionDialogProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const createSession = useCreateChatSession();
  const activePersonas = personas.filter((p) => p.active);

  async function handleCreate() {
    try {
      const session = await createSession.mutateAsync({ persona_id: selected });
      onCreated(session.id);
      onOpenChange(false);
      setSelected(null);
    } catch (err) {
      toast.error(getErrorMessage(err, "Nie udało się utworzyć rozmowy."));
    }
  }

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Nowa rozmowa"
      description="Wybierz ogólną rozmowę (odpowie właściwy trener) albo konkretną personę."
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Anuluj
          </Button>
          <Button onClick={handleCreate} disabled={createSession.isPending}>
            Rozpocznij
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-2">
        <button
          type="button"
          onClick={() => setSelected(null)}
          className={cn(
            "rounded-md border p-3 text-left text-sm transition-colors hover:bg-accent",
            selected === null && "border-primary bg-accent"
          )}
        >
          <div className="font-medium">Ogólna rozmowa</div>
          <div className="text-xs text-muted-foreground">
            System sam wybierze, kto z Twoich trenerów odpowie na dany temat.
          </div>
        </button>
        {activePersonas.map((persona) => (
          <button
            key={persona.id}
            type="button"
            onClick={() => setSelected(persona.id)}
            className={cn(
              "rounded-md border p-3 text-left text-sm transition-colors hover:bg-accent",
              selected === persona.id && "border-primary bg-accent"
            )}
          >
            <div className="font-medium">{persona.name}</div>
            <div className="text-xs text-muted-foreground">{PERSONA_TYPE_LABELS[persona.type]}</div>
          </button>
        ))}
        {activePersonas.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nie masz jeszcze aktywnych person — dodaj jedną w zakładce Persony.
          </p>
        ) : null}
      </div>
    </ResponsiveDialog>
  );
}
