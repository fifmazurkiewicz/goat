import { ResponsiveDialog } from "@/components/common/ResponsiveDialog";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useUserProfile } from "@/hooks/useUserProfile";
import { DETAIL_LEVEL_EXPLANATIONS, DETAIL_LEVEL_LABELS, PERSONA_TYPE_LABELS } from "@/lib/persona-labels";
import type { Persona } from "@/types/api";

interface PersonaConfigDialogProps {
  persona: Persona | null;
  onOpenChange: (open: boolean) => void;
  onEdit?: (persona: Persona) => void;
}

const GOAL_LABELS: Record<string, string> = {
  lose_weight: "Redukcja wagi",
  build_muscle: "Budowa masy mięśniowej",
  improve_endurance: "Poprawa wytrzymałości",
  general_health: "Ogólne zdrowie",
  sport_specific: "Cel specyficzny dla dyscypliny",
};

/** "Zobacz pełną konfigurację" — user_profile + pełny prompt + poziom szczegółowości. */
export function PersonaConfigDialog({ persona, onOpenChange, onEdit }: PersonaConfigDialogProps) {
  const { data: userProfile } = useUserProfile();

  return (
    <ResponsiveDialog
      open={Boolean(persona)}
      onOpenChange={onOpenChange}
      title={persona?.name ?? ""}
      description={persona ? PERSONA_TYPE_LABELS[persona.type] : undefined}
      className="sm:max-w-xl"
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Zamknij
          </Button>
          {persona && onEdit ? <Button onClick={() => onEdit(persona)}>Edytuj prompt</Button> : null}
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
                <div>{userProfile?.primary_goal ? GOAL_LABELS[userProfile.primary_goal] : "—"}</div>
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
              Jak ma odpowiadać (prompt)
            </div>
            <p className="mt-1 whitespace-pre-line text-sm">{persona.system_prompt}</p>
          </div>

          {persona.persona_constraints ? (
            <>
              <Separator />
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Twarde ograniczenia
                </div>
                <p className="mt-1 whitespace-pre-line text-sm">{persona.persona_constraints}</p>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </ResponsiveDialog>
  );
}
