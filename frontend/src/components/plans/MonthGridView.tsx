import { ChevronLeft, ChevronRight } from "lucide-react";
import { isSameDay } from "date-fns";
import { pl } from "date-fns/locale";
import { DayPicker, type DayButtonProps } from "react-day-picker";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PlanItem } from "@/types/api";

interface MonthGridViewProps {
  month: Date;
  selectedDate: Date;
  onSelectDate: (date: Date) => void;
  onMonthChange: (month: Date) => void;
  items: PlanItem[];
}

function makeDayButton(items: PlanItem[]) {
  function CustomDayButton({ day, modifiers, className, ...rest }: DayButtonProps) {
    const hasItems = items.some((item) => isSameDay(new Date(item.item_date), day.date));
    return (
      <button
        type="button"
        className={cn(
          buttonVariants({ variant: "ghost" }),
          "relative h-11 w-full min-w-0 p-0 font-normal aria-selected:opacity-100",
          modifiers.selected && "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
          modifiers.today && !modifiers.selected && "bg-accent text-accent-foreground",
          modifiers.outside && "text-muted-foreground opacity-50",
          className
        )}
        {...rest}
      >
        {day.date.getDate()}
        {hasItems ? (
          <span
            className={cn(
              "absolute bottom-1.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full",
              modifiers.selected ? "bg-primary-foreground" : "bg-primary"
            )}
          />
        ) : null}
      </button>
    );
  }
  return CustomDayButton;
}

/**
 * Month grid — `react-day-picker` / shadcn `Calendar` ONLY for `MonthGridView`
 * (docs/technical/frontend.md section 5). Used on phone and desktop. A dot under
 * the day signals that a `plan_item` exists without opening a panel.
 */
export function MonthGridView({ month, selectedDate, onSelectDate, onMonthChange, items }: MonthGridViewProps) {
  return (
    <DayPicker
      mode="single"
      locale={pl}
      month={month}
      onMonthChange={onMonthChange}
      selected={selectedDate}
      onSelect={(date) => date && onSelectDate(date)}
      showOutsideDays
      className="w-full p-0"
      classNames={{
        months: "flex flex-col",
        month: "flex flex-col gap-4 w-full",
        month_caption: "flex justify-center pt-1 relative items-center w-full capitalize",
        caption_label: "text-sm font-medium",
        nav: "flex items-center justify-between absolute inset-x-0 top-0",
        button_previous: cn(buttonVariants({ variant: "outline" }), "h-7 w-7 bg-transparent p-0 opacity-70 hover:opacity-100"),
        button_next: cn(buttonVariants({ variant: "outline" }), "h-7 w-7 bg-transparent p-0 opacity-70 hover:opacity-100"),
        month_grid: "w-full border-collapse",
        weekdays: "flex",
        weekday: "text-muted-foreground flex-1 font-normal text-[0.8rem] capitalize",
        week: "flex w-full mt-1",
        day: "text-center text-sm p-0 relative flex-1",
      }}
      components={{
        Chevron: ({ orientation, ...rest }) =>
          orientation === "left" ? <ChevronLeft className="h-4 w-4" {...rest} /> : <ChevronRight className="h-4 w-4" {...rest} />,
        DayButton: makeDayButton(items),
      }}
    />
  );
}
