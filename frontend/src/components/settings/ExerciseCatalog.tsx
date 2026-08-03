import { useMemo, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ExerciseDetailDialog } from "@/components/settings/ExerciseDetailDialog";
import { ExerciseGrid } from "@/components/settings/ExerciseGrid";
import { ExerciseSearchBar } from "@/components/settings/ExerciseSearchBar";
import { useExercises } from "@/hooks/useExercises";
import type { Exercise } from "@/types/api";

/**
 * Katalog ćwiczeń (ADR-14) — pozostaje w zakładce Ustawienia (decyzja usera wbrew
 * alternatywnej rekomendacji). Filtrowanie po kategorii/query PO STRONIE KLIENTA
 * (docs/technical/frontend.md sekcja 7a).
 */
export function ExerciseCatalog() {
  const { data: exercises, isLoading } = useExercises();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [openExercise, setOpenExercise] = useState<Exercise | null>(null);

  const categories = useMemo(() => {
    const set = new Set<string>();
    (exercises ?? []).forEach((ex) => ex.categories.forEach((c) => set.add(c)));
    return Array.from(set).sort();
  }, [exercises]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return (exercises ?? []).filter((ex) => {
      const matchesCategory = category === "all" || ex.categories.includes(category);
      const matchesQuery =
        !normalizedQuery ||
        ex.name.toLowerCase().includes(normalizedQuery) ||
        ex.categories.some((c) => c.toLowerCase().includes(normalizedQuery));
      return matchesCategory && matchesQuery;
    });
  }, [exercises, query, category]);

  return (
    <section>
      <h2 className="text-xl font-semibold">Katalog ćwiczeń</h2>
      <p className="mt-1 max-w-[70ch] text-sm text-muted-foreground">
        Widoczny dla person typu trener motoryczny i trener badmintona — opisy wykonania najpopularniejszych
        ćwiczeń, ze zdjęciem poglądowym.
      </p>

      <div className="mt-4">
        <ExerciseSearchBar
          query={query}
          onQueryChange={setQuery}
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
          <ExerciseGrid exercises={filtered} onOpen={setOpenExercise} />
        )}
      </div>

      <ExerciseDetailDialog exercise={openExercise} onOpenChange={(open) => !open && setOpenExercise(null)} />
    </section>
  );
}
