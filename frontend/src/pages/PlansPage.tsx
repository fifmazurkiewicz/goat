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
import {
  CalendarViewSwitcher,
  resolveCalendarView,
  type CalendarView,
} from "@/components/plans/CalendarViewSwitcher";
import { GeneratePlanCta } from "@/components/plans/GeneratePlanCta";
import { PlanGenerationPersonaProgress } from "@/components/plans/PlanGenerationPersonaProgress";
import { PlanGenerationBanner } from "@/components/plans/PlanGenerationBanner";
import { usePersonas } from "@/hooks/usePersonas";
import { usePlanRange } from "@/hooks/usePlans";
import { useIsMobile } from "@/hooks/useMediaQuery";
import { PAGE_SHELL_CLASS, PAGE_TITLE_CLASS } from "@/lib/layout";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";

const DATE_FORMAT = "yyyy-MM-dd";

/**
 * `activeMonth`/`activeDate` from URL search params (linkable) — docs/technical/
 * frontend.md section 5. `PlansPage` does NOT initiate generation polling — that lives in
 * AppShell (`usePlanGenerationPolling`); here we only read the resulting state.
 */
export default function PlansPage() {
  const isMobile = useIsMobile();
  const [searchParams, setSearchParams] = useSearchParams();
  const [manualView, setManualView] = useState<CalendarView | null>(null);

  const view = resolveCalendarView(isMobile, manualView);

  const selectedDate = useMemo(() => {
    const raw = searchParams.get("date");
    const parsed = raw ? parseISO(raw) : null;
    return parsed && isValid(parsed) ? parsed : new Date();
  }, [searchParams]);

  function setSelectedDate(date: Date) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("date", format(date, DATE_FORMAT));
      return next;
    });
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
    <div className={PAGE_SHELL_CLASS}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className={`${PAGE_TITLE_CLASS} capitalize`}>Plan {view === "week" ? "tygodnia" : "miesiąca"}</h1>
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
        personas={personas}
        onPrev={handlePrev}
        onNext={handleNext}
      />

      {!isLoading && generationStatus !== "generating" && (!data?.plan || data.plan.status === "error" || data.plan.status === "partial_ready") ? (
        <div className="mt-6">
          <GeneratePlanCta startDate={format(rangeStart, DATE_FORMAT)} />
        </div>
      ) : null}
    </div>
  );
}
