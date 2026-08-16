import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

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
import { usePersonas } from "@/hooks/usePersonas";
import { useAllResults, useResults } from "@/hooks/useResults";
import { resultCategoryTabsFromPersonas } from "@/lib/result-categories";
import { PAGE_SHELL_CLASS, PAGE_TITLE_CLASS } from "@/lib/layout";
import type { ResultCategory } from "@/types/api";

/**
 * Taby kategorii z aktywnych person usera (+ kategorie z już zapisanych wyników),
 * wykres liniowy per metryka (ADR-9) i tabela z edycją inline
 * (docs/technical/frontend.md sekcja 6).
 */
export default function ResultsPage() {
  const { data: personasData, isLoading: personasLoading } = usePersonas();
  const { data: allResults } = useAllResults();
  const categoryTabs = useMemo(
    () =>
      resultCategoryTabsFromPersonas(personasData?.items ?? [], {
        categoriesWithData: (allResults ?? []).map((r) => r.category),
      }),
    [personasData?.items, allResults]
  );

  const [category, setCategory] = useState<ResultCategory | null>(null);
  const [metric, setMetric] = useState<string | null>(null);

  useEffect(() => {
    if (categoryTabs.length === 0) {
      setCategory(null);
      return;
    }
    if (!category || !categoryTabs.some((t) => t.key === category)) {
      setCategory(categoryTabs[0].key);
      setMetric(null);
    }
  }, [categoryTabs, category]);

  const activeCategory = category ?? categoryTabs[0]?.key ?? null;
  const { data: results, isLoading } = useResults(activeCategory);
  const resultsLoading = !activeCategory || isLoading;

  const metrics = useMemo(() => Array.from(new Set((results ?? []).map((r) => r.metric))), [results]);
  const selectedMetric = metric && metrics.includes(metric) ? metric : (metrics[0] ?? null);

  if (personasLoading) {
    return (
      <div className={PAGE_SHELL_CLASS}>
        <h1 className={PAGE_TITLE_CLASS}>Wyniki</h1>
        <p className="mt-6 text-sm text-muted-foreground">Ładowanie…</p>
      </div>
    );
  }

  if (categoryTabs.length === 0 || !activeCategory) {
    return (
      <div className={PAGE_SHELL_CLASS}>
        <h1 className={`mb-6 ${PAGE_TITLE_CLASS}`}>Wyniki</h1>
        <p className="text-sm text-muted-foreground">
          Kategorie wyników zależą od Twoich person.{" "}
          <Link to="/personas" className="underline underline-offset-2 hover:text-foreground">
            Dodaj personę
          </Link>
          , żeby zobaczyć Trening, Dietę, Badminton itd.
        </p>
      </div>
    );
  }

  return (
    <div className={PAGE_SHELL_CLASS}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className={PAGE_TITLE_CLASS}>Wyniki</h1>
        <AddResultDialog category={activeCategory} />
      </div>

      <Tabs
        value={activeCategory}
        onValueChange={(value) => {
          setCategory(value as ResultCategory);
          setMetric(null);
        }}
      >
        <TabsList>
          {categoryTabs.map((tab) => (
            <TabsTrigger key={tab.key} value={tab.key}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {resultsLoading ? (
        <p className="mt-6 text-sm text-muted-foreground">Ładowanie…</p>
      ) : (
        <div className="mt-6 space-y-6">
          <div className="rounded-md border p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Trend</h2>
              {metrics.length > 0 ? (
                <Select value={selectedMetric ?? undefined} onValueChange={setMetric}>
                  <SelectTrigger className="w-full max-w-56">
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

          <ResultsTable results={results ?? []} category={activeCategory} />
        </div>
      )}
    </div>
  );
}
