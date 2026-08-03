import { format, isSameDay } from "date-fns";
import { pl } from "date-fns/locale";

import { cn } from "@/lib/utils";
import type { PlanItem } from "@/types/api";

interface WeekAgendaViewProps {
  days: Date[];
  items: PlanItem[];
  selectedDate: Date;
  onSelectDate: (date: Date) => void;
}

/**
 * DEFAULT <768px — custom (date-fns), NIE grid (docs/technical/frontend.md sekcja 5).
 * Lista agendowa (nie siatka) — czytelniejsza na wąskim ekranie niż 7-kolumnowy grid.
 */
export function WeekAgendaView({ days, items, selectedDate, onSelectDate }: WeekAgendaViewProps) {
  return (
    <div className="flex flex-col gap-2">
      {days.map((day) => {
        const dayItems = items.filter((item) => isSameDay(new Date(item.item_date), day));
        const isSelected = isSameDay(day, selectedDate);

        return (
          <button
            key={day.toISOString()}
            type="button"
            onClick={() => onSelectDate(day)}
            className={cn(
              "rounded-md border p-3 text-left transition-colors",
              isSelected ? "border-primary bg-accent" : "hover:bg-accent/50"
            )}
          >
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium capitalize">{format(day, "EEEE, d MMMM", { locale: pl })}</span>
              {isSameDay(day, new Date()) ? <span className="text-xs text-primary">Dziś</span> : null}
            </div>
            {dayItems.length === 0 ? (
              <p className="mt-1 text-xs text-muted-foreground">Brak zaplanowanych pozycji</p>
            ) : (
              <ul className="mt-1 space-y-0.5">
                {dayItems.map((item) => (
                  <li key={item.id} className="text-xs text-muted-foreground">
                    <span className="text-accent-foreground/80">{item.item_type}</span> · {item.content.title}
                  </li>
                ))}
              </ul>
            )}
          </button>
        );
      })}
    </div>
  );
}
