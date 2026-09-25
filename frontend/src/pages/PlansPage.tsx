import { useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { endOfMonth, format, isValid, parseISO, startOfMonth } from "date-fns";
import { pl } from "date-fns/locale";
import { Badge } from "@/components/ui/badge";
import { MonthGridView } from "@/components/plans/MonthGridView";
import { DayPlanDetail } from "@/components/plans/DayPlanDetail";
import { PlanGenerationDialog } from "@/components/plans/PlanGenerationDialog";
import { PlanGenerationPersonaProgress } from "@/components/plans/PlanGenerationPersonaProgress";
import { PlanGenerationBanner } from "@/components/plans/PlanGenerationBanner";
import { usePersonas } from "@/hooks/usePersonas";
import { usePlanRange } from "@/hooks/usePlans";
import { PAGE_SHELL_CLASS, PAGE_TITLE_CLASS } from "@/lib/layout";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";
const DATE_FORMAT = "yyyy-MM-dd";
export default function PlansPage() {
  const [searchParams, setSearchParams] = useSearchParams(); const [dialogOpen, setDialogOpen] = useState(false); const detailRef = useRef<HTMLDivElement>(null);
  const selectedDate = useMemo(() => { const raw = searchParams.get("date"); const parsed = raw ? parseISO(raw) : null; return parsed && isValid(parsed) ? parsed : new Date(); }, [searchParams]);
  const rangeStart = startOfMonth(selectedDate); const rangeEnd = endOfMonth(selectedDate);
  const { data, isLoading } = usePlanRange(format(rangeStart, DATE_FORMAT), format(rangeEnd, DATE_FORMAT)); const generationStatus = usePlanGenerationStore((state) => state.status); const generationBreakdown = usePlanGenerationStore((state) => state.breakdown); const { data: personasData } = usePersonas(); const personas = personasData?.items ?? []; const items = data?.items ?? [];
  function setSelectedDate(date: Date) { setSearchParams((prev) => { const next = new URLSearchParams(prev); next.set("date", format(date, DATE_FORMAT)); return next; }); requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })); }
  return <div className={PAGE_SHELL_CLASS}><div className="mb-6 flex flex-wrap items-center justify-between gap-3"><div><h1 className={PAGE_TITLE_CLASS + " capitalize"}>Plan miesiąca</h1><p className="capitalize text-muted-foreground">{format(selectedDate, "LLLL yyyy", { locale: pl })}</p></div><div className="flex items-center gap-2">{data?.plan ? <Badge variant={data.plan.status === "ready" ? "default" : "outline"}>{data.plan.status === "ready" ? "Plan gotowy" : data.plan.status === "partial_ready" ? "Plan częściowy" : data.plan.status === "generating" ? "Generowanie…" : "Błąd generowania"}</Badge> : null}<button type="button" className="min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground" onClick={() => setDialogOpen(true)}>{data?.plan ? "Przebuduj plan" : "Ułóż plan"}</button></div></div><PlanGenerationBanner />{(generationStatus === "generating" || generationStatus === "partial_ready") && generationBreakdown.length > 0 ? <PlanGenerationPersonaProgress breakdown={generationBreakdown} personas={personas} planItems={items} jobStatus={generationStatus === "partial_ready" ? "partial_ready" : "generating"} /> : null}<MonthGridView month={selectedDate} selectedDate={selectedDate} onSelectDate={setSelectedDate} onMonthChange={setSelectedDate} items={items} /><div ref={detailRef} className="mt-6 scroll-mt-6 rounded-lg border bg-card p-4"><DayPlanDetail date={selectedDate} items={items.filter((item) => item.item_date === format(selectedDate, DATE_FORMAT))} personas={personas} /></div>{!isLoading ? <PlanGenerationDialog open={dialogOpen} onOpenChange={setDialogOpen} defaultDate={selectedDate} personas={personas} /> : null}</div>;
}
