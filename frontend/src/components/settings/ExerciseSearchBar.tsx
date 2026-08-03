import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface ExerciseSearchBarProps {
  query: string;
  onQueryChange: (query: string) => void;
  categories: string[];
  activeCategory: string;
  onCategoryChange: (category: string) => void;
}

/**
 * Filter-chipy kategorii `overflow-x-auto` na mobile (NIE `flex-wrap` — zajmuje zbyt
 * dużo wysokości ekranu przed treścią), docs/technical/frontend.md sekcja 7a.
 */
export function ExerciseSearchBar({
  query,
  onQueryChange,
  categories,
  activeCategory,
  onCategoryChange,
}: ExerciseSearchBarProps) {
  return (
    <div className="space-y-3">
      <div className="max-w-sm space-y-1.5">
        <label htmlFor="exercise-search" className="text-sm font-medium">
          Szukaj ćwiczenia
        </label>
        <Input
          id="exercise-search"
          placeholder="np. biceps, przysiad, sprint 10m"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
        />
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {["all", ...categories].map((category) => (
          <button
            key={category}
            type="button"
            onClick={() => onCategoryChange(category)}
            className={cn(
              "shrink-0 whitespace-nowrap rounded-full border px-3 py-1 text-xs font-medium transition-colors",
              activeCategory === category ? "bg-primary text-primary-foreground" : "hover:bg-accent"
            )}
          >
            {category === "all" ? "Wszystkie" : category}
          </button>
        ))}
      </div>
    </div>
  );
}
