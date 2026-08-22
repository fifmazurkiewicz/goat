import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { cn } from "@/lib/utils";
import type { ConsultDetail } from "@/types/api";

interface ConsultDetailsProps {
  details: ConsultDetail[];
  className?: string;
}

/**
 * Podgląd konsultacji Goata (`consult_persona`, spec 2026-08-22) — lista rozwijanych
 * elementów pod wiadomością Goata (sibling bąbelki, jak ToolResultChip). Domyślnie
 * zwinięte; `type="multiple"` — roundtable pozwala porównywać kilka odpowiedzi naraz.
 * Styl „podglądu źródła", nie osobna wiadomość trenera — ADR-17 nietknięty.
 */
export function ConsultDetails({ details, className }: ConsultDetailsProps) {
  if (details.length === 0) return null;
  return (
    <Accordion
      type="multiple"
      className={cn(
        "w-full max-w-[80%] self-start overflow-hidden rounded-md border bg-muted/30 text-xs",
        className
      )}
    >
      {details.map((detail, index) => (
        <AccordionItem
          key={detail.toolCallId || `consult-${index}`}
          value={detail.toolCallId || `consult-${index}`}
          className="border-b last:border-b-0"
        >
          <AccordionTrigger className="min-h-11 px-3 py-2 text-xs font-medium no-underline hover:no-underline">
            <span className="text-left">
              {detail.personaLabel} odpowiedział{detail.personaLabel.endsWith("a") ? "a" : ""}
            </span>
          </AccordionTrigger>
          <AccordionContent className="max-h-80 space-y-2 overflow-y-auto px-3 pb-3 pt-0">
            {detail.question ? (
              <p className="text-muted-foreground">
                <span className="font-medium">Pytanie: </span>
                {detail.question}
              </p>
            ) : null}
            <p className="whitespace-pre-line leading-relaxed">{detail.answer}</p>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
