import { format } from "date-fns";
import { pl } from "date-fns/locale";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ActualResultsPanel } from "@/components/plans/ActualResultsPanel";
import { PlanItemTable } from "@/components/plans/PlanItemTable";
import { useCreateChatSession } from "@/hooks/useChatSessions";
import { useIsMobile } from "@/hooks/useMediaQuery";
import { ApiError } from "@/lib/api-client";
import { PERSONA_TYPE_LABELS } from "@/lib/persona-labels";
import type { Persona, PlanItem } from "@/types/api";

interface DayPanelProps {
  date: Date | null;
  items: PlanItem[];
  personas: Persona[];
  onOpenChange: (open: boolean) => void;
}

/**
 * `Sheet` responsywny (bottom mobile / side desktop) — jeden komponent, różny `side`
 * (docs/technical/frontend.md sekcja 5).
 */
export function DayPanel({ date, items, personas, onOpenChange }: DayPanelProps) {
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const createSession = useCreateChatSession();

  async function handleTalkToCoach(item: PlanItem) {
    try {
      const summary = `${item.content.title}\n\n${item.content.rows
        .map((row) => row.join(" | "))
        .join("\n")}${item.content.notes ? `\n\n${item.content.notes}` : ""}`;
      const session = await createSession.mutateAsync({
        persona_id: item.persona_id,
        initial_message: `Porozmawiajmy o tym planie:\n${summary}`,
      });
      onOpenChange(false);
      navigate(`/chat/${session.id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nie udało się utworzyć rozmowy.");
    }
  }

  return (
    <Sheet open={Boolean(date)} onOpenChange={onOpenChange}>
      <SheetContent side={isMobile ? "bottom" : "right"} className="flex h-[92vh] flex-col overflow-y-auto sm:h-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{date ? format(date, "EEEE, d MMMM yyyy", { locale: pl }) : ""}</SheetTitle>
          <SheetDescription>Zaplanowane i zrealizowane tego dnia.</SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-6 py-4">
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Brak zaplanowanych pozycji na ten dzień.</p>
          ) : (
            items.map((item) => {
              const persona = personas.find((p) => p.id === item.persona_id);
              return (
                <div key={item.id} className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {item.item_type}
                      </div>
                      <div className="text-lg font-semibold">{item.content.title}</div>
                      {persona ? (
                        <div className="text-xs text-muted-foreground">
                          {persona.name} · {PERSONA_TYPE_LABELS[persona.type]}
                        </div>
                      ) : null}
                    </div>
                    <Button type="button" size="sm" variant="secondary" onClick={() => handleTalkToCoach(item)}>
                      Porozmawiaj z trenerem
                    </Button>
                  </div>
                  <PlanItemTable content={item.content} />
                  {item.content.notes ? (
                    <p className="text-xs text-muted-foreground">{item.content.notes}</p>
                  ) : null}
                </div>
              );
            })
          )}

          <Separator />

          <div>
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Zrealizowane
            </div>
            {date ? <ActualResultsPanel date={format(date, "yyyy-MM-dd")} /> : null}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
