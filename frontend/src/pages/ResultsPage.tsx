import { useMemo, useState } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AddResultDialog } from "@/components/results/AddResultDialog";
import { ResultsChart } from "@/components/results/ResultsChart";
import { ResultsTable } from "@/components/results/ResultsTable";
import { useResults } from "@/hooks/useResults";
import type { ResultCategory } from "@/types/api";

const CATEGORY_TABS: { key: ResultCategory; label: string }[] = [
  { key: "strength", label: "Siłownia" },
  { key: "diet", label: "Dieta" },
  { key: "swimming", label: "Basen" },
  { key: "triathlon", label: "Triathlon" },
  { key: "badminton", label: "Badminton" },
];

/**
 * Taby kategorii, wykres liniowy per metryka (ADR-9) i tabela z edycją inline
 * (docs/technical/frontend.md sekcja 6).
 */
export default function ResultsPage() {
  const [category, setCategory] = useState<ResultCategory>("strength");
  const [metric, setMetric] = useState<string | null>(null);
  const { data: results, isLoading } = useResults(category);

  const metrics = useMemo(() => Array.from(new Set((results ?? []).map((r) => r.metric))), [results]);
  const selectedMetric = metric && metrics.includes(metric) ? metric : (metrics[0] ?? null);

  return (
    <div className="container py-10">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">Wyniki</h1>
        <AddResultDialog category={category} />
      </div>

      <Tabs
        value={category}
        onValueChange={(value) => {
          setCategory(value as ResultCategory);
          setMetric(null);
        }}
      >
        <TabsList>
          {CATEGORY_TABS.map((tab) => (
            <TabsTrigger key={tab.key} value={tab.key}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {isLoading ? (
        <p className="mt-6 text-sm text-muted-foreground">Ładowanie…</p>
      ) : (
        <div className="mt-6 space-y-6">
          <div className="rounded-md border p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Trend</h2>
              {metrics.length > 0 ? (
                <Select value={selectedMetric ?? undefined} onValueChange={setMetric}>
                  <SelectTrigger className="w-56">
                    <SelectValue placeholder="Wybierz metrykę" />
                  </SelectTrigger>
                  <SelectContent>
                    {metrics.map((m) => (
                      <SelectItem key={m} value={m}>
                        {m}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : null}
            </div>
            {selectedMetric ? (
              <ResultsChart results={results ?? []} metric={selectedMetric} />
            ) : (
              <p className="text-sm text-muted-foreground">Brak wyników w tej kategorii.</p>
            )}
          </div>

          <ResultsTable results={results ?? []} category={category} />
        </div>
      )}
    </div>
  );
}
