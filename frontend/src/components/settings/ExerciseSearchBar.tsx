import { useMemo, useRef } from "react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface ExerciseSearchBarProps {
  query: string;
  onQueryChange: (query: string) => void;
  onQuerySubmit: () => void;
  categories: string[];
  activeCategory: string;
  onCategoryChange: (category: string) => void;
}

const TRAINING_TYPES = new Set([
  "Cardio",
  "Plyometryka",
  "Rozciąganie",
  "Siłowe",
  "Strongman",
  "Trójbój",
  "Podnoszenie ciężarów",
]);

/**
 * Kategoria jako `Select` z grupowaniem (Partie mięśniowe / Typ treningu) — przy ~24
 * kategoriach po imporcie free-exercise-db chipy `overflow-x-auto` byłyby nieodkrywalne
 * poza viewportem (spójnie z wyborem `Select` dla gotowców persony).
 * Nazwy i opisy importu są po polsku; `name_en` nadal działa w wyszukiwarce.
 */
export function ExerciseSearchBar({
  query,
  onQueryChange,
  onQuerySubmit,
  categories,
  activeCategory,
  onCategoryChange,
}: ExerciseSearchBarProps) {
  const { muscles, trainingTypes } = useMemo(() => {
    const sorted = [...categories].sort((a, b) => a.localeCompare(b, "pl"));
    return {
      muscles: sorted.filter((c) => !TRAINING_TYPES.has(c)),
      trainingTypes: sorted.filter((c) => TRAINING_TYPES.has(c)),
    };
  }, [categories]);

  const inputRef = useRef<HTMLInputElement>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    inputRef.current?.blur();
    onQuerySubmit();
  }

  return (
    <form className="space-y-3" onSubmit={handleSubmit}>
      <div className="max-w-sm space-y-1.5">
        <label htmlFor="exercise-search" className="text-sm font-medium">
          Szukaj ćwiczenia
        </label>
        <div className="flex gap-2">
          <Input
            ref={inputRef}
            id="exercise-search"
            placeholder="np. przysiad, klatka, squat"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
          />
          <Button type="submit" className="shrink-0">
            Szukaj
          </Button>
        </div>
      </div>
      <div className="max-w-xs">
        <Select value={activeCategory} onValueChange={onCategoryChange}>
          <SelectTrigger aria-label="Filtr kategorii">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Wszystkie kategorie</SelectItem>
            {muscles.length > 0 && (
              <SelectGroup>
                <SelectLabel>Partie mięśniowe</SelectLabel>
                {muscles.map((category) => (
                  <SelectItem key={category} value={category}>
                    {category}
                  </SelectItem>
                ))}
              </SelectGroup>
            )}
            {trainingTypes.length > 0 && (
              <SelectGroup>
                <SelectLabel>Typ treningu</SelectLabel>
                {trainingTypes.map((category) => (
                  <SelectItem key={category} value={category}>
                    {category}
                  </SelectItem>
                ))}
              </SelectGroup>
            )}
          </SelectContent>
        </Select>
      </div>
    </form>
  );
}
