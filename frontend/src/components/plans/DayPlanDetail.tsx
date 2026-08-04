import { format } from "date-fns";
import { pl } from "date-fns/locale";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ActualResultsPanel } from "@/components/plans/ActualResultsPanel";
import { PlanItemTable } from "@/components/plans/PlanItemTable";
import { useCreateChatSession } from "@/hooks/useChatSessions";
import { getErrorMessage } from "@/lib/api-client";
import { formatPlanRowForChat } from "@/lib/plan-item-content";
import { PERSONA_TYPE_LABELS } from "@/lib/persona-labels";
import type { Persona, PlanItem } from "@/types/api";

interface DayPlanDetailProps {
  date: Date;
  items: PlanItem[];
  personas: Persona[];
  /** Ukryj nagłówek daty — np. w rozwiniętym wierszu tygodnia. */
  showHeader?: boolean;
}

/** Szczegóły planu na dany dzień — inline (bez Sheet z prawej strony). */
export function DayPlanDetail({ date, items, personas, showHeader = true }: DayPlanDetailProps) {
  const navigate = useNavigate();
  const createSession = useCreateChatSession();

  async function handleTalkToCoach(item: PlanItem) {
    try {
      const rowsText = item.content.rows
        .map((row) => formatPlanRowForChat(row, item.content.columns))
        .join("\n");
      const summary = `${item.content.title}\n\n${rowsText}${item.content.notes ? `\n\n${item.content.notes}` : ""}`;
      const session = await createSession.mutateAsync({
        persona_id: item.persona_id,
        title: item.content.title?.trim() || undefined,
      });
      navigate(`/chat/${session.id}`, {
        state: { autoSend: `Porozmawiajmy o tym planie:\n${summary}` },
      });
    } catch (err) {
      toast.error(getErrorMessage(err, "Nie udało się utworzyć rozmowy."));
    }
  }

  return (
    <div className="space-y-6">
      {showHeader ? (
        <div>
          <h3 className="text-base font-semibold capitalize">{format(date, "EEEE, d MMMM yyyy", { locale: pl })}</h3>
          <p className="text-sm text-muted-foreground">Zaplanowane i zrealizowane tego dnia.</p>
        </div>
      ) : null}

      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Brak zaplanowanych pozycji na ten dzień.</p>
      ) : (
        items.map((item) => {
          const persona = personas.find((p) => p.id === item.persona_id);
          return (
            <div key={item.id} className="space-y-2 rounded-md border bg-card p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
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
                <Button type="button" size="sm" variant="secondary" onClick={() => void handleTalkToCoach(item)}>
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
        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Zrealizowane</div>
        <ActualResultsPanel date={format(date, "yyyy-MM-dd")} />
      </div>
    </div>
  );
}
