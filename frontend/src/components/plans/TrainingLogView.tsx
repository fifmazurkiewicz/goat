import { useMemo, useState } from "react";
import { format, parseISO } from "date-fns";
import { pl } from "date-fns/locale";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useTrainingLogData } from "@/hooks/useTrainingLog";
import { personaAvatarColor } from "@/lib/persona-labels";
import { personaResultCategory } from "@/lib/result-categories";
import { buildTrainingLog, type LogDay, type LogWeek } from "@/lib/training-log";
import { cn } from "@/lib/utils";
import type { Persona } from "@/types/api";

const ALL = "all";
const WEEKDAY_LABELS = ["Pn", "Wt", "Śr", "Cz", "Pt", "Sb", "Nd"];
const STATUS_LABELS: Record<LogDay["status"], string> = {
  done: "wykonane",
  missed: "zaplanowane, bez wpisu",
  planned: "zaplanowane",
  empty: "brak planu i wpisów",
};

interface TrainingLogViewProps {
  personas: Persona[];
  selectedDate: string;
  onSelectDate: (date: Date) => void;
}

/** Default filter: the first active persona logging into `strength` (training), else everything. */
function defaultPersonaFilter(personas: Persona[]): string {
  return personas.find((persona) => persona.active && personaResultCategory(persona) === "strength")?.id ?? ALL;
}

function formatKm(km: number): string {
  return Number.isInteger(km) ? String(km) : km.toFixed(1).replace(".", ",");
}

/**
 * "Since start" log — week rows (newest first), each day shows plan vs done at a glance:
 * filled = logged, dashed = planned but missed, outlined = planned ahead, blank = nothing.
 * Monochrome on purpose; colour only for persona dots and today's ring.
 */
export function TrainingLogView({ personas, selectedDate, onSelectDate }: TrainingLogViewProps) {
  const today = useMemo(() => new Date(), []);
  const activePersonas = useMemo(() => personas.filter((persona) => persona.active), [personas]);
  const [manualFilter, setManualFilter] = useState<string | null>(null);
  const filterId = manualFilter ?? defaultPersonaFilter(activePersonas);
  const { start, items, results, isLoading } = useTrainingLogData(today);

  const personaById = useMemo(() => new Map(personas.map((persona) => [persona.id, persona])), [personas]);
  const log = useMemo(
    () =>
      buildTrainingLog({
        start,
        today,
        items,
        results,
        filter: filterId === ALL ? null : { personaId: filterId, persona: personaById.get(filterId) ?? null },
      }),
    [start, today, items, results, filterId, personaById]
  );
  const weeks = useMemo(() => [...log.weeks].reverse(), [log.weeks]);
  const { stats } = log;

  return (
    <section aria-labelledby="training-log-heading" className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 id="training-log-heading" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Dziennik od startu
          </h2>
          <p className="font-mono text-sm">
            {format(parseISO(log.start), "d MMM yyyy", { locale: pl })} – {format(today, "d MMM yyyy", { locale: pl })}
          </p>
        </div>
        <Select value={filterId} onValueChange={setManualFilter}>
          <SelectTrigger className="w-full sm:w-56" aria-label="Filtr persony">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Wszystkie persony</SelectItem>
            {activePersonas.map((persona) => (
              <SelectItem key={persona.id} value={persona.id}>
                {persona.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <dl className="grid grid-cols-2 border-y sm:grid-cols-4">
        <Stat label="Dni od startu" value={String(stats.daysSinceStart)} hint={`${stats.weeks} tyg.`} />
        <Stat label="Dni z wpisem" value={String(stats.doneDays)} hint={`śr. ${String(stats.avgDonePerWeek).replace(".", ",")} / tydz.`} />
        <Stat
          label="Realizacja planu"
          value={stats.plannedPastDays ? `${Math.round((stats.donePlannedDays / stats.plannedPastDays) * 100)}%` : "–"}
          hint={`${stats.donePlannedDays} z ${stats.plannedPastDays} dni`}
        />
        <Stat label="Dystans" value={stats.km ? formatKm(stats.km) : "–"} unit={stats.km ? "km" : undefined} hint="z wpisów w km" />
      </dl>

      <Legend />

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Ładowanie dziennika…</p>
      ) : (
        <div className="max-w-xl space-y-1">
          <div aria-hidden="true" className="grid grid-cols-[repeat(7,minmax(0,1fr))_3.25rem] gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            {WEEKDAY_LABELS.map((label) => (
              <span key={label} className="text-center">
                {label}
              </span>
            ))}
            <span className="text-center">
              Plan
            </span>
          </div>
          {weeks.map((week, index) => {
            const month = week.days[6].date.slice(0, 7);
            const showMonth = index === 0 || weeks[index - 1].days[6].date.slice(0, 7) !== month;
            return (
              <div key={week.weekStart}>
                {showMonth ? (
                  <div className="pb-1 pt-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {format(parseISO(`${month}-01`), "LLLL yyyy", { locale: pl })}
                  </div>
                ) : null}
                <WeekRow week={week} selectedDate={selectedDate} personaById={personaById} onSelectDate={onSelectDate} />
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function Stat({ label, value, unit, hint }: { label: string; value: string; unit?: string; hint: string }) {
  return (
    <div className="border-b px-3 py-3 odd:border-r sm:border-b-0 sm:border-r sm:last:border-r-0">
      <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-3xl font-light tabular-nums">
        {value}
        {unit ? <span className="ml-0.5 text-sm text-muted-foreground">{unit}</span> : null}
      </dd>
      <dd className="text-xs text-muted-foreground">{hint}</dd>
    </div>
  );
}

function Legend() {
  const swatch = "inline-block h-3 w-3 rounded-sm align-middle";
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Legenda">
      <li><span className={cn(swatch, "bg-foreground")} /> wykonane</li>
      <li><span className={cn(swatch, "border border-foreground")} /> zaplanowane</li>
      <li><span className={cn(swatch, "border border-dashed border-muted-foreground")} /> pominięte</li>
      <li><span className={cn(swatch, "bg-muted")} /> bez planu</li>
      <li><span className="font-mono text-foreground">+</span> poza planem</li>
    </ul>
  );
}

function WeekRow({
  week,
  selectedDate,
  personaById,
  onSelectDate,
}: {
  week: LogWeek;
  selectedDate: string;
  personaById: Map<string, Persona>;
  onSelectDate: (date: Date) => void;
}) {
  return (
    <div className="grid grid-cols-[repeat(7,minmax(0,1fr))_3.25rem] gap-1">
      {week.days.map((day) => (
        <DayCell
          key={day.date}
          day={day}
          selected={day.date === selectedDate}
          personaById={personaById}
          onSelect={() => onSelectDate(parseISO(day.date))}
        />
      ))}
      <div className="flex flex-col items-center justify-center font-mono text-[11px] tabular-nums">
        <span className="sr-only">Tydzień: wykonane {week.donePlannedDays} z {week.plannedDays} zaplanowanych dni</span>
        <span aria-hidden="true">
          {week.donePlannedDays}/{week.plannedDays}
        </span>
        <span aria-hidden="true" className="mt-0.5 flex gap-px">
          {Array.from({ length: Math.min(week.plannedDays, 7) }, (_, i) => (
            <span
              key={i}
              className={cn("h-1.5 w-1.5", i < week.donePlannedDays ? "bg-foreground" : "border border-muted-foreground")}
            />
          ))}
        </span>
        {week.km ? <span aria-hidden="true" className="text-muted-foreground">{formatKm(week.km)} km</span> : null}
      </div>
    </div>
  );
}

function DayCell({
  day,
  selected,
  personaById,
  onSelect,
}: {
  day: LogDay;
  selected: boolean;
  personaById: Map<string, Persona>;
  onSelect: () => void;
}) {
  if (!day.inRange) {
    return <div aria-hidden="true" className="aspect-square" />;
  }
  const planned = day.plannedPersonaIds.map((id) => personaById.get(id)).filter((p): p is Persona => Boolean(p));
  const letter = planned[0]?.name.trim().charAt(0).toUpperCase() ?? "";
  const label = [
    format(parseISO(day.date), "EEEE d MMMM", { locale: pl }),
    STATUS_LABELS[day.status],
    day.offPlan ? "poza planem" : null,
    day.km ? `${formatKm(day.km)} km` : null,
    planned.length ? `plan: ${planned.map((p) => p.name).join(", ")}` : null,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <div>
      <button
        type="button"
        aria-label={label}
        aria-pressed={selected}
        onClick={onSelect}
        className={cn(
          "relative flex aspect-square w-full flex-col items-center justify-center rounded-sm text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 motion-reduce:transition-none",
          day.status === "done" && "bg-foreground text-background",
          day.status === "planned" && "border border-foreground",
          day.status === "missed" && "border border-dashed border-muted-foreground text-muted-foreground",
          day.status === "empty" && "bg-muted/60 text-muted-foreground",
          day.isToday && "ring-2 ring-primary ring-offset-1 ring-offset-background",
          selected && !day.isToday && "ring-2 ring-foreground ring-offset-1 ring-offset-background"
        )}
      >
        <span className="absolute left-1 top-0.5 text-[9px] leading-none opacity-70">
          {day.isToday ? "dziś" : Number(day.date.slice(8))}
        </span>
        {day.km ? (
          <span className="font-mono text-sm font-semibold leading-none sm:text-base">
            {formatKm(day.km)}
            <span className="text-[8px] font-normal">km</span>
          </span>
        ) : (
          <span className="font-mono text-sm font-semibold leading-none sm:text-base">{day.offPlan ? "+" : letter}</span>
        )}
        {planned.length > 1 ? (
          <span aria-hidden="true" className="absolute bottom-1 flex gap-0.5">
            {planned.map((persona) => (
              <span key={persona.id} className={cn("h-1 w-1 rounded-full", personaAvatarColor(persona.id))} />
            ))}
          </span>
        ) : null}
      </button>
    </div>
  );
}
