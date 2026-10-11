import { useMemo } from "react";
import { format, parseISO } from "date-fns";
import { pl } from "date-fns/locale";

import { PlanItemTable } from "@/components/plans/PlanItemTable";
import { ResultsTable } from "@/components/results/ResultsTable";
import { buildTrainingSessions } from "@/lib/training-sessions";
import type { Persona, Result, ResultCategory } from "@/types/api";

interface TrainingSessionListProps {
  results: Result[];
  personas: Persona[];
  category: ResultCategory;
}

function entriesLabel(count: number): string {
  if (count === 1) return "wpis";
  const lastDigit = count % 10;
  const lastTwo = count % 100;
  return lastDigit >= 2 && lastDigit <= 4 && (lastTwo < 12 || lastTwo > 14) ? "wpisy" : "wpisów";
}

/**
 * `/results` training categories (ADR-25): one card per day, rows from `results.details`
 * rendered by `PlanItemTable` (table on desktop, cards on mobile, catalog links). Editing
 * reuses `ResultsTable` inside a collapsible section.
 */
export function TrainingSessionList({ results, personas, category }: TrainingSessionListProps) {
  const sessions = useMemo(() => buildTrainingSessions(results), [results]);
  const personaName = useMemo(() => new Map(personas.map((p) => [p.id, p.name])), [personas]);

  if (sessions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Brak zapisanych sesji — zgłoś trening w czacie albo dodaj go ręcznie.
      </p>
    );
  }

  return (
    <ul className="space-y-4" aria-label="Sesje treningowe">
      {sessions.map((session) => {
        const who = [
          ...new Set(session.personaIds.map((id) => (id ? (personaName.get(id) ?? "Persona") : "Goat"))),
        ];
        return (
          <li key={session.date} className="rounded-lg border bg-card p-4">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-base font-semibold first-letter:uppercase">
                {format(parseISO(session.date), "EEEE, d MMMM yyyy", { locale: pl })}
              </h2>
              <p className="text-xs text-muted-foreground">
                {session.results.length} {entriesLabel(session.results.length)} · {who.join(", ")}
              </p>
            </div>
            <PlanItemTable content={session.content} />
            <details className="mt-3">
              <summary className="cursor-pointer rounded-sm text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                Edytuj wpisy
              </summary>
              <div className="mt-2">
                <ResultsTable results={session.results} category={category} />
              </div>
            </details>
          </li>
        );
      })}
    </ul>
  );
}
