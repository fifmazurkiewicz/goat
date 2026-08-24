import { useEffect, useMemo, useState } from "react";

import { ExerciseGrid } from "@/components/settings/ExerciseGrid";
import { ExerciseSearchBar } from "@/components/settings/ExerciseSearchBar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useExercises } from "@/hooks/useExercises";
import {
  IDLE_SAMPLE_SIZE,
  pickRandomExercises,
  visibleExercises,
} from "@/lib/exercise-catalog";
import type { Exercise } from "@/types/api";

/**
 * Exercise catalog (ADR-14) — lives in the Settings tab. Without a query: 3 random
 * cards + "Show others"; once a word is typed the client-side filter applies
 * (frontend.md §7a).
 */
export function ExerciseCatalog() {
  const { data: exercises, isLoading } = useExercises();
  const [query, setQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [category, setCategory] = useState("all");
  const [sample, setSample] = useState<Exercise[]>([]);
  const isSearching = searchTerm.trim().length > 0;

  const categories = useMemo(() => {
    const set = new Set<string>();
    (exercises ?? []).forEach((ex) => ex.categories.forEach((c) => set.add(c)));
    return Array.from(set).sort();
  }, [exercises]);

  const pool = useMemo(() => {
    const all = exercises ?? [];
    if (category === "all") return all;
    return all.filter((ex) => ex.categories.includes(category));
  }, [exercises, category]);

  useEffect(() => {
    setSample(pickRandomExercises(pool, IDLE_SAMPLE_SIZE));
  }, [pool]);

  const shown = useMemo(
    () =>
      visibleExercises({
        all: exercises ?? [],
        sample,
        query: searchTerm,
        category,
      }),
    [exercises, sample, searchTerm, category],
  );

  function handleSubmit() {
    setSearchTerm(query.trim());
  }

  return (
    <section>
      <h2 className="text-xl font-semibold">Katalog ćwiczeń</h2>
      <p className="mt-1 max-w-[70ch] text-sm text-muted-foreground">
        Szukaj po nazwie (PL lub EN). Na starcie trzy losowe ćwiczenia — reszta katalogu
        pojawia się po klikku „Szukaj”.
      </p>

      <div className="mt-4">
        <ExerciseSearchBar
          query={query}
          onQueryChange={setQuery}
          onQuerySubmit={handleSubmit}
          categories={categories}
          activeCategory={category}
          onCategoryChange={setCategory}
        />
      </div>

      <div className="mt-5">
        {isLoading ? (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-64 w-full" />
            ))}
          </div>
        ) : (
          <>
            <ExerciseGrid exercises={shown} />
            {!isSearching && pool.length > IDLE_SAMPLE_SIZE ? (
              <Button
                type="button"
                variant="outline"
                className="mt-4"
                onClick={() => setSample(pickRandomExercises(pool, IDLE_SAMPLE_SIZE))}
              >
                Pokaż inne
              </Button>
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}
