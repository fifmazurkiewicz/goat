import { Dumbbell } from "lucide-react";

import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { Exercise } from "@/types/api";

interface ExerciseGridProps {
  exercises: Exercise[];
  onOpen: (exercise: Exercise) => void;
}

const LEVEL_LABELS: Record<Exercise["level"], string> = {
  beginner: "Podstawowy",
  intermediate: "Średni",
  advanced: "Zaawansowany",
};

/**
 * `grid-cols-1` <768px / `grid-cols-3` desktop, opis skrócony `line-clamp-2` (nie pełny
 * `text-align: justify` — nieczytelne w wąskiej karcie), docs/technical/frontend.md sekcja 11.
 */
export function ExerciseGrid({ exercises, onOpen }: ExerciseGridProps) {
  if (exercises.length === 0) {
    return <p className="text-sm text-muted-foreground">Brak ćwiczeń dla tego wyszukiwania.</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {exercises.map((exercise) => (
        <Card key={exercise.id} className="cursor-pointer overflow-hidden p-0" onClick={() => onOpen(exercise)}>
          <AspectRatio ratio={16 / 9} className="bg-muted">
            {exercise.photo_path ? (
              <img src={exercise.photo_path} alt={exercise.name} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                <Dumbbell className="h-8 w-8" />
              </div>
            )}
          </AspectRatio>
          <div className="flex flex-col gap-1.5 p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="font-semibold leading-tight">{exercise.name}</div>
              <Badge variant="outline" className="shrink-0">
                {LEVEL_LABELS[exercise.level]}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-1">
              {exercise.categories.map((category) => (
                <Badge key={category} variant="secondary">
                  {category}
                </Badge>
              ))}
            </div>
            <p className="line-clamp-2 text-sm text-muted-foreground">{exercise.short_description}</p>
          </div>
        </Card>
      ))}
    </div>
  );
}
