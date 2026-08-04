import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  addMonths,
  addWeeks,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isValid,
  parseISO,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import { pl } from "date-fns/locale";

import { Badge } from "@/components/ui/badge";
import { CalendarViewSwitcher, type CalendarView } from "@/components/plans/CalendarViewSwitcher";
import { DayPanel } from "@/components/plans/DayPanel";
import { GeneratePlanCta } from "@/components/plans/GeneratePlanCta";
import { PlanGenerationPersonaProgress } from "@/components/plans/PlanGenerationPersonaProgress";
import { PlanGenerationBanner } from "@/components/plans/PlanGenerationBanner";
import { usePersonas } from "@/hooks/usePersonas";
import { usePlanRange } from "@/hooks/usePlans";
import { useIsMobile } from "@/hooks/useMediaQuery";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";

const DATE_FORMAT = "yyyy-MM-dd";

/**
 * `activeMonth`/`activeDate` z URL search params (linkowalne) — docs/technical/
 * frontend.md sekcja 5. `PlansPage` NIE inicjuje pollingu generowania — to żyje w
 * AppShell (`usePlanGenerationPolling`), tu tylko czytamy wynikowy stan.
 */
export default function PlansPage() {
  const isMobile = useIsMobile();
  const [searchParams, setSearchParams] = useSearchParams();
  const [manualView, setManualView] = useState<CalendarView>("month");

  const view: CalendarView = isMobile ? "week" : manualView;

  const selectedDate = useMemo(() => {
    const raw = searchParams.get("date");
    const parsed = raw ? parseISO(raw) : null;
    return parsed && isValid(parsed) ? parsed : new Date();
  }, [searchParams]);

  const [isDayPanelOpen, setIsDayPanelOpen] = useState(false);

  function setSelectedDate(date: Date) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("date", format(date, DATE_FORMAT));
      return next;
    });
    setIsDayPanelOpen(true);
  }

  const weekDays = useMemo(
    () => eachDayOfInterval({ start: startOfWeek(selectedDate, { weekStartsOn: 1 }), end: endOfWeek(selectedDate, { weekStartsOn: 1 }) }),
    [selectedDate]
  );

  const rangeStart = view === "week" ? startOfWeek(selectedDate, { weekStartsOn: 1 }) : startOfMonth(selectedDate);
  const rangeEnd = view === "week" ? endOfWeek(selectedDate, { weekStartsOn: 1 }) : endOfMonth(selectedDate);

  const { data, isLoading } = usePlanRange(format(rangeStart, DATE_FORMAT), format(rangeEnd, DATE_FORMAT));
  const generationStatus = usePlanGenerationStore((state) => state.status);
  const generationBreakdown = usePlanGenerationStore((state) => state.breakdown);
  const { data: personasData } = usePersonas();
  const personas = personasData?.items ?? [];

  const items = data?.items ?? [];
  const selectedDayItems = items.filter((item) => item.item_date === format(selectedDate, DATE_FORMAT));

  function handlePrev() {
    setSelectedDate(view === "week" ? addWeeks(selectedDate, -1) : addMonths(selectedDate, -1));
  }

  function handleNext() {
    setSelectedDate(view === "week" ? addWeeks(selectedDate, 1) : addMonths(selectedDate, 1));
  }

  const periodLabel =
    view === "week"
      ? `${format(rangeStart, "d MMM", { locale: pl })} – ${format(rangeEnd, "d MMM yyyy", { locale: pl })}`
      : format(selectedDate, "LLLL yyyy", { locale: pl });

  return (
    <div className="container py-10">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-semibold capitalize tracking-tight">Plan {view === "week" ? "tygodnia" : "miesiąca"}</h1>
          <p className="capitalize text-muted-foreground">{periodLabel}</p>
        </div>
        {data?.plan ? (
          <Badge variant={data.plan.status === "ready" ? "default" : "outline"}>
            {data.plan.status === "ready"
              ? "Plan gotowy"
              : data.plan.status === "partial_ready"
                ? "Plan częściowy"
                : data.plan.status === "generating"
                  ? "Generowanie…"
                  : "Błąd generowania"}
          </Badge>
        ) : null}
      </div>

      <PlanGenerationBanner />

      {(generationStatus === "generating" || generationStatus === "partial_ready") &&
      generationBreakdown.length > 0 ? (
        <PlanGenerationPersonaProgress
          breakdown={generationBreakdown}
          personas={personas}
          planItems={items}
          jobStatus={generationStatus === "partial_ready" ? "partial_ready" : "generating"}
        />
      ) : null}

      <CalendarViewSwitcher
        view={view}
        onViewChange={setManualView}
        selectedDate={selectedDate}
        onSelectDate={setSelectedDate}
        weekDays={weekDays}
        month={selectedDate}
        onMonthChange={setSelectedDate}
        items={items}
        onPrev={handlePrev}
        onNext={handleNext}
      />

      {!isLoading && generationStatus !== "generating" && (!data?.plan || data.plan.status === "error" || data.plan.status === "partial_ready") ? (
        <div className="mt-6">
          <GeneratePlanCta startDate={format(rangeStart, DATE_FORMAT)} />
        </div>
      ) : null}

      <DayPanel
        date={isDayPanelOpen ? selectedDate : null}
        items={selectedDayItems}
        personas={personas}
        onOpenChange={setIsDayPanelOpen}
      />
    </div>
  );
}
