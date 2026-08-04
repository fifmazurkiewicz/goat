import { ResponsiveDialog } from "@/components/common/ResponsiveDialog";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useUserProfile } from "@/hooks/useUserProfile";
import { DETAIL_LEVEL_EXPLANATIONS, DETAIL_LEVEL_LABELS, PERSONA_TYPE_LABELS } from "@/lib/persona-labels";
import { PRIMARY_GOAL_LABELS } from "@/lib/user-profile-labels";
import type { Persona } from "@/types/api";

interface PersonaConfigDialogProps {
  persona: Persona | null;
  onOpenChange: (open: boolean) => void;
  onEdit?: (persona: Persona) => void;
}

/** Konfiguracja persony — warstwa usera (styl, profil, detail). Bez safety/constraints. */
export function PersonaConfigDialog({ persona, onOpenChange, onEdit }: PersonaConfigDialogProps) {
  const { data: userProfile } = useUserProfile();

  return (
    <ResponsiveDialog
      open={Boolean(persona)}
      onOpenChange={onOpenChange}
      title={persona?.name ?? ""}
      description={
        persona
          ? `${PERSONA_TYPE_LABELS[persona.type]}. To ustawienia, które kontrolujesz — aplikacja zawsze stosuje własne zasady bezpieczeństwa.`
          : undefined
      }
      className="sm:max-w-xl"
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Zamknij
          </Button>
          {persona && onEdit ? <Button onClick={() => onEdit(persona)}>Edytuj styl</Button> : null}
        </>
      }
    >
      {persona ? (
        <div className="space-y-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Twoje dane, które widzi ta persona
            </div>
            <div className="mt-2 grid grid-cols-3 gap-3 text-sm">
              <div>
                <div className="text-[11px] text-muted-foreground">Wzrost</div>
                <div className="tabular-nums">{userProfile?.height_cm ? `${userProfile.height_cm} cm` : "—"}</div>
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">Waga</div>
                <div className="tabular-nums">{userProfile?.weight_kg ? `${userProfile.weight_kg} kg` : "—"}</div>
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">Cel</div>
                <div>{userProfile?.primary_goal ? PRIMARY_GOAL_LABELS[userProfile.primary_goal] : "—"}</div>
              </div>
            </div>
          </div>

          <Separator />

          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Poziom szczegółowości
            </div>
            <p className="mt-1 text-sm">
              {DETAIL_LEVEL_LABELS[persona.detail_level]} — {DETAIL_LEVEL_EXPLANATIONS[persona.detail_level]}
            </p>
          </div>

          <Separator />

          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Styl i zakres pomocy
            </div>
            <p className="mt-1 whitespace-pre-line text-sm">{persona.system_prompt}</p>
          </div>
        </div>
      ) : null}
    </ResponsiveDialog>
  );
}
