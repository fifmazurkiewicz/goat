import { format, isSameDay } from "date-fns";
import { pl } from "date-fns/locale";

import { DayPlanDetail } from "@/components/plans/DayPlanDetail";
import { cn } from "@/lib/utils";
import type { Persona, PlanItem } from "@/types/api";

interface WeekAgendaViewProps {
  days: Date[];
  items: PlanItem[];
  selectedDate: Date;
  onSelectDate: (date: Date) => void;
  personas: Persona[];
}

/**
 * Week view — list of days with the day's plan detail expanded inline under the selected day.
 */
export function WeekAgendaView({ days, items, selectedDate, onSelectDate, personas }: WeekAgendaViewProps) {
  return (
    <div className="flex flex-col gap-2">
      {days.map((day) => {
        const dayItems = items.filter((item) => isSameDay(new Date(item.item_date), day));
        const isSelected = isSameDay(day, selectedDate);

        return (
          <div
            key={day.toISOString()}
            className={cn(
              "rounded-md border transition-colors",
              isSelected ? "border-primary bg-accent/30" : "hover:bg-accent/20"
            )}
          >
            <button
              type="button"
              onClick={() => onSelectDate(day)}
              className="w-full p-3 text-left"
            >
              <div className="flex items-baseline justify-between">
                <span className="text-sm font-medium capitalize">
                  {format(day, "EEEE, d MMMM", { locale: pl })}
                </span>
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

            {isSelected ? (
              <div className="border-t px-3 pb-4 pt-2">
                <DayPlanDetail date={day} items={dayItems} personas={personas} showHeader={false} />
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
