import {
  addDays,
  addMonths,
  differenceInCalendarWeeks,
  endOfMonth,
  endOfWeek,
  format,
  isAfter,
  isBefore,
  parseISO,
  startOfMonth,
  startOfWeek,
} from "date-fns";

import { personaResultCategory } from "@/lib/result-categories";
import type { Persona, PlanItem, Result } from "@/types/api";

const DATE_FORMAT = "yyyy-MM-dd";
const WEEK_OPTIONS = { weekStartsOn: 1 } as const;
/** Upper bound on how far back the log reaches — keeps the per-month plan fetches bounded. */
export const LOG_MAX_MONTHS_BACK = 12;

/**
 * - `done` — at least one result logged that day (plan executed, or work off plan)
 * - `missed` — planned, the day has passed, nothing logged
 * - `planned` — planned for today or later
 * - `empty` — nothing planned, nothing logged
 */
export type LogDayStatus = "done" | "missed" | "planned" | "empty";

export interface LogDay {
  date: string;
  status: LogDayStatus;
  /** Logged without a plan item that day. */
  offPlan: boolean;
  /** Distinct persona ids with a plan item that day (first-seen order). */
  plannedPersonaIds: string[];
  /** Summed results in km that day (0 when none). */
  km: number;
  resultCount: number;
  inRange: boolean;
  isToday: boolean;
}

export interface LogWeek {
  weekStart: string;
  days: LogDay[];
  plannedDays: number;
  doneDays: number;
  /** Planned days that were also done. */
  donePlannedDays: number;
  km: number;
}

export interface LogStats {
  daysSinceStart: number;
  weeks: number;
  doneDays: number;
  plannedPastDays: number;
  donePlannedDays: number;
  avgDonePerWeek: number;
  km: number;
}

export interface TrainingLog {
  start: string;
  end: string;
  weeks: LogWeek[];
  stats: LogStats;
}

export type LogPersonaFilter = { personaId: string; persona: Persona | null } | null;

/** First logged result (clamped to `LOG_MAX_MONTHS_BACK`); start of current month when nothing is logged. */
export function logRangeStart(results: Pick<Result, "logged_date">[], today: Date): Date {
  const floor = startOfMonth(addMonths(today, -LOG_MAX_MONTHS_BACK));
  let earliest = startOfMonth(today);
  for (const result of results) {
    const date = parseISO(result.logged_date);
    if (isBefore(date, earliest)) earliest = date;
  }
  return isBefore(earliest, floor) ? floor : earliest;
}

/** Whole calendar months covering `[start, end]` — one `GET /plans` range per month (one plan per month). */
export function monthRanges(start: Date, end: Date): { startDate: string; endDate: string }[] {
  const ranges: { startDate: string; endDate: string }[] = [];
  for (let month = startOfMonth(start); !isAfter(month, end); month = addMonths(month, 1)) {
    ranges.push({ startDate: format(month, DATE_FORMAT), endDate: format(endOfMonth(month), DATE_FORMAT) });
  }
  return ranges;
}

function matchesFilter(filter: LogPersonaFilter) {
  const category = filter?.persona ? personaResultCategory(filter.persona) : null;
  return {
    item: (item: PlanItem) => !filter || item.persona_id === filter.personaId,
    result: (result: Result) =>
      !filter || result.source_persona_id === filter.personaId || (category !== null && result.category === category),
  };
}

function isKm(unit: string): boolean {
  return unit.trim().toLowerCase() === "km";
}

/** Week-by-week plan vs done log from `start` to `today` (whole weeks, Monday first). */
export function buildTrainingLog(params: {
  start: Date;
  today: Date;
  items: PlanItem[];
  results: Result[];
  filter?: LogPersonaFilter;
}): TrainingLog {
  const { start, today, items, results, filter = null } = params;
  const matches = matchesFilter(filter);
  const startKey = format(start, DATE_FORMAT);
  const todayKey = format(today, DATE_FORMAT);

  const plannedByDate = new Map<string, string[]>();
  for (const item of items) {
    if (!matches.item(item)) continue;
    const ids = plannedByDate.get(item.item_date) ?? [];
    if (!ids.includes(item.persona_id)) ids.push(item.persona_id);
    plannedByDate.set(item.item_date, ids);
  }

  const resultsByDate = new Map<string, { count: number; km: number }>();
  for (const result of results) {
    if (!matches.result(result)) continue;
    const entry = resultsByDate.get(result.logged_date) ?? { count: 0, km: 0 };
    entry.count += 1;
    if (isKm(result.unit)) entry.km += result.value;
    resultsByDate.set(result.logged_date, entry);
  }

  const weeks: LogWeek[] = [];
  const lastWeekStart = startOfWeek(today, WEEK_OPTIONS);
  for (let weekStart = startOfWeek(start, WEEK_OPTIONS); !isAfter(weekStart, lastWeekStart); weekStart = addDays(weekStart, 7)) {
    const days: LogDay[] = [];
    for (let offset = 0; offset < 7; offset += 1) {
      const date = addDays(weekStart, offset);
      const key = format(date, DATE_FORMAT);
      const inRange = key >= startKey && key <= format(endOfWeek(today, WEEK_OPTIONS), DATE_FORMAT);
      const planned = inRange ? (plannedByDate.get(key) ?? []) : [];
      const logged = inRange ? resultsByDate.get(key) : undefined;
      const status: LogDayStatus = logged
        ? "done"
        : planned.length === 0
          ? "empty"
          : key < todayKey
            ? "missed"
            : "planned";
      days.push({
        date: key,
        status,
        offPlan: Boolean(logged) && planned.length === 0,
        plannedPersonaIds: planned,
        km: logged?.km ?? 0,
        resultCount: logged?.count ?? 0,
        inRange,
        isToday: key === todayKey,
      });
    }
    weeks.push({
      weekStart: format(weekStart, DATE_FORMAT),
      days,
      plannedDays: days.filter((day) => day.plannedPersonaIds.length > 0).length,
      doneDays: days.filter((day) => day.status === "done").length,
      donePlannedDays: days.filter((day) => day.status === "done" && day.plannedPersonaIds.length > 0).length,
      km: days.reduce((sum, day) => sum + day.km, 0),
    });
  }

  const pastDays = weeks.flatMap((week) => week.days).filter((day) => day.inRange && day.date <= todayKey);
  const weekCount = Math.max(1, differenceInCalendarWeeks(today, start, WEEK_OPTIONS) + 1);
  const doneDays = pastDays.filter((day) => day.status === "done").length;
  return {
    start: startKey,
    end: todayKey,
    weeks,
    stats: {
      daysSinceStart: pastDays.length,
      weeks: weekCount,
      doneDays,
      plannedPastDays: pastDays.filter((day) => day.plannedPersonaIds.length > 0).length,
      donePlannedDays: pastDays.filter((day) => day.status === "done" && day.plannedPersonaIds.length > 0).length,
      avgDonePerWeek: Math.round((doneDays / weekCount) * 10) / 10,
      km: pastDays.reduce((sum, day) => sum + day.km, 0),
    },
  };
}
