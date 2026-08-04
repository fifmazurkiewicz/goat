import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { PERSONA_TYPE_LABELS } from "@/lib/persona-labels";
import type { Persona, PlanGenerationJobPersonaBreakdown, PlanItem } from "@/types/api";

const STATUS_LABELS: Record<PlanGenerationJobPersonaBreakdown["status"], string> = {
  pending: "Oczekuje",
  running: "Generuje…",
  done: "Gotowe",
  failed: "Błąd",
};

function personaLabel(persona: Persona | undefined, personaId: string): string {
  if (!persona) return personaId.slice(0, 8);
  const role = PERSONA_TYPE_LABELS[persona.type] ?? persona.type;
  return persona.name?.trim() ? `${persona.name} · ${role}` : role;
}

function StatusIcon({ status }: { status: PlanGenerationJobPersonaBreakdown["status"] }) {
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
  if (status === "done") return <CheckCircle2 className="h-4 w-4 text-green-600" />;
  if (status === "failed") return <XCircle className="h-4 w-4 text-destructive" />;
  return <Circle className="h-4 w-4 text-muted-foreground" />;
}

interface PlanGenerationPersonaProgressProps {
  breakdown: PlanGenerationJobPersonaBreakdown[];
  personas: Persona[];
  planItems: PlanItem[];
  jobStatus: "generating" | "partial_ready" | "ready";
}

/**
 * Podgląd postępu per persona — draft każdej persony widoczny w kalendarzu zaraz po `done`,
 * finalny plan po harmonizacji (status planu `ready`).
 */
export function PlanGenerationPersonaProgress({
  breakdown,
  personas,
  planItems,
  jobStatus,
}: PlanGenerationPersonaProgressProps) {
  if (breakdown.length === 0) return null;

  const personaById = new Map(personas.map((p) => [p.id, p]));
  const itemsByPersona = planItems.reduce<Map<string, PlanItem[]>>((acc, item) => {
    const list = acc.get(item.persona_id) ?? [];
    list.push(item);
    acc.set(item.persona_id, list);
    return acc;
  }, new Map());

  const doneCount = breakdown.filter((b) => b.status === "done").length;
  const harmonizing = doneCount === breakdown.length && jobStatus === "generating";

  return (
    <div className="mb-6 space-y-3 rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Postęp trenerów</h2>
        {harmonizing ? (
          <Badge variant="secondary" className="gap-1">
            <Loader2 className="h-3 w-3 animate-spin" />
            Harmonizacja planu…
          </Badge>
        ) : (
          <span className="text-xs text-muted-foreground">
            {doneCount}/{breakdown.length} person gotowych
          </span>
        )}
      </div>

      <Accordion type="multiple" className="w-full">
        {breakdown.map((entry) => {
          const persona = personaById.get(entry.persona_id);
          const items = itemsByPersona.get(entry.persona_id) ?? [];
          const previewDates = [...new Set(items.map((i) => i.item_date))].sort().slice(0, 5);

          return (
            <AccordionItem key={entry.persona_id} value={entry.persona_id}>
              <AccordionTrigger className="hover:no-underline">
                <div className="flex flex-1 items-center gap-3 pr-2 text-left">
                  <StatusIcon status={entry.status} />
                  <span className="flex-1 text-sm font-medium">{personaLabel(persona, entry.persona_id)}</span>
                  <Badge variant="outline" className="shrink-0 text-xs">
                    {STATUS_LABELS[entry.status]}
                  </Badge>
                  {items.length > 0 ? (
                    <span className="hidden text-xs text-muted-foreground sm:inline">
                      {items.length} pozycji
                    </span>
                  ) : null}
                </div>
              </AccordionTrigger>
              <AccordionContent>
                {entry.status === "failed" && entry.last_error ? (
                  <p className="mb-2 text-xs text-destructive">{entry.last_error}</p>
                ) : null}
                {items.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    {entry.status === "running"
                      ? "Trwa generowanie — pozycje pojawią się w kalendarzu po zapisie."
                      : entry.status === "pending"
                        ? "Czeka w kolejce."
                        : "Brak pozycji w tym okresie."}
                  </p>
                ) : (
                  <ul className="space-y-1 text-xs text-muted-foreground">
                    {items.slice(0, 8).map((item) => (
                      <li key={item.id}>
                        <span className="tabular-nums">{item.item_date}</span> — {item.content.title}
                      </li>
                    ))}
                    {items.length > 8 ? (
                      <li>… i {items.length - 8} więcej (zobacz w kalendarzu)</li>
                    ) : null}
                    {previewDates.length > 0 && jobStatus !== "ready" ? (
                      <li className="pt-1 text-[11px] italic">
                        Wersja robocza persony — po harmonizacji plan może się lekko zmienić.
                      </li>
                    ) : null}
                  </ul>
                )}
              </AccordionContent>
            </AccordionItem>
          );
        })}
      </Accordion>
    </div>
  );
}
