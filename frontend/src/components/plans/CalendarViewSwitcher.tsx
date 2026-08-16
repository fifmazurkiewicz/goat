import { isSameDay } from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { DayPlanDetail } from "@/components/plans/DayPlanDetail";
import { MonthGridView } from "@/components/plans/MonthGridView";
import { WeekAgendaView } from "@/components/plans/WeekAgendaView";
import { useIsMobile } from "@/hooks/useMediaQuery";
import { cn } from "@/lib/utils";
import type { Persona, PlanItem } from "@/types/api";

export type CalendarView = "week" | "month";

interface CalendarViewSwitcherProps {
  view: CalendarView;
  onViewChange: (view: CalendarView) => void;
  selectedDate: Date;
  onSelectDate: (date: Date) => void;
  weekDays: Date[];
  month: Date;
  onMonthChange: (month: Date) => void;
  items: PlanItem[];
  personas: Persona[];
  onPrev: () => void;
  onNext: () => void;
}

/**
 * Week<768px (default) / Month desktop, wybierane wg breakpointu (`matchMedia`) +
 * ręczny override na desktopie (docs/technical/frontend.md sekcja 5).
 */
export function CalendarViewSwitcher({
  view,
  onViewChange,
  selectedDate,
  onSelectDate,
  weekDays,
  month,
  onMonthChange,
  items,
  personas,
  onPrev,
  onNext,
}: CalendarViewSwitcherProps) {
  const isMobile = useIsMobile();

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {!isMobile ? (
          <div className="inline-flex rounded-md border p-1">
            {(["week", "month"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => onViewChange(option)}
                className={cn(
                  "rounded-sm px-3 py-1 text-sm transition-colors",
                  view === option ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"
                )}
              >
                {option === "week" ? "Tydzień" : "Miesiąc"}
              </button>
            ))}
          </div>
        ) : (
          <div />
        )}
        <div className="flex gap-2">
          <Button type="button" variant="secondary" className="min-h-11" onClick={onPrev}>
            <ChevronLeft className="mr-1 h-4 w-4" /> Poprzedni
          </Button>
          <Button type="button" variant="secondary" className="min-h-11" onClick={onNext}>
            Następny <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>

      {view === "week" ? (
        <WeekAgendaView
          days={weekDays}
          items={items}
          selectedDate={selectedDate}
          onSelectDate={onSelectDate}
          personas={personas}
        />
      ) : (
        <>
          <MonthGridView
            month={month}
            selectedDate={selectedDate}
            onSelectDate={onSelectDate}
            onMonthChange={onMonthChange}
            items={items}
          />
          <div className="mt-4 rounded-lg border bg-card p-4">
            <DayPlanDetail
              date={selectedDate}
              items={items.filter((item) => isSameDay(new Date(item.item_date), selectedDate))}
              personas={personas}
            />
          </div>
        </>
      )}
    </div>
  );
}
