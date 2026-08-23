import { useDeferredValue, useMemo, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ExerciseGrid } from "@/components/settings/ExerciseGrid";
import { ExerciseSearchBar } from "@/components/settings/ExerciseSearchBar";
import { useExercises } from "@/hooks/useExercises";

/**
 * Katalog ćwiczeń (ADR-14) — pozostaje w zakładce Ustawienia. Filtrowanie po
 * kategorii/query PO STRONIE KLIENTA (docs/technical/frontend.md sekcja 7a);
 * karta prowadzi do strony `/exercises/:slug` (dialog usunięty 2026-08-23).
 */
export function ExerciseCatalog() {
  const { data: exercises, isLoading } = useExercises();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  // ~870 kart po imporcie free-exercise-db — odroczone filtrowanie, żeby wpisywanie
  // nie re-koncylidowało siatki przy każdym klawiszu (słabsze mobile).
  const deferredQuery = useDeferredValue(query);

  const categories = useMemo(() => {
    const set = new Set<string>();
    (exercises ?? []).forEach((ex) => ex.categories.forEach((c) => set.add(c)));
    return Array.from(set).sort();
  }, [exercises]);

  const filtered = useMemo(() => {
    const normalizedQuery = deferredQuery.trim().toLowerCase();
    return (exercises ?? []).filter((ex) => {
      const matchesCategory = category === "all" || ex.categories.includes(category);
      const matchesQuery =
        !normalizedQuery ||
        ex.name.toLowerCase().includes(normalizedQuery) ||
        ex.name_en?.toLowerCase().includes(normalizedQuery) ||
        ex.categories.some((c) => c.toLowerCase().includes(normalizedQuery));
      return matchesCategory && matchesQuery;
    });
  }, [exercises, deferredQuery, category]);

  return (
    <section>
      <h2 className="text-xl font-semibold">Katalog ćwiczeń</h2>
      <p className="mt-1 max-w-[70ch] text-sm text-muted-foreground">
        Widoczny dla person typu trener motoryczny i trener badmintona — opisy wykonania najpopularniejszych
        ćwiczeń, ze zdjęciem poglądowym. Większość pozycji pochodzi z otwartego katalogu free-exercise-db
        (opisy przetłumaczone na polski).
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
          <ExerciseGrid exercises={filtered} />
        )}
      </div>
    </section>
  );
}
