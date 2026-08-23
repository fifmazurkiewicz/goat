import { Dumbbell } from "lucide-react";
import { Link } from "react-router-dom";

import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { exercisePhotoSrc } from "@/lib/exercise-photo";
import type { Exercise } from "@/types/api";

interface ExerciseGridProps {
  exercises: Exercise[];
}

const LEVEL_LABELS: Record<Exercise["level"], string> = {
  beginner: "Podstawowy",
  intermediate: "Średni",
  advanced: "Zaawansowany",
};

/**
 * Karta = `Link` do `/exercises/:slug` (ADR-14 nowelizacja 2026-08-23 — jedna strona
 * szczegółów dla katalogu i planów, dialog usunięty). `grid-cols-1` <768px /
 * `grid-cols-3` desktop, opis `line-clamp-2`, lazy-loading zdjęć (import ~870 pozycji).
 */
export function ExerciseGrid({ exercises }: ExerciseGridProps) {
  if (exercises.length === 0) {
    return <p className="text-sm text-muted-foreground">Brak ćwiczeń dla tego wyszukiwania.</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {exercises.map((exercise) => {
        const photoSrc = exercisePhotoSrc(exercise.photo_path);
        return (
        <Link
          key={exercise.id}
          to={`/exercises/${exercise.slug}`}
          className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg"
        >
          <Card className="h-full cursor-pointer overflow-hidden p-0 transition-colors hover:bg-accent/40">
            <AspectRatio ratio={3 / 2} className="bg-muted">
              {photoSrc ? (
                <img
                  src={photoSrc}
                  alt={exercise.name}
                  loading="lazy"
                  decoding="async"
                  className="h-full w-full object-cover"
                />
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
        </Link>
        );
      })}
    </div>
  );
}
