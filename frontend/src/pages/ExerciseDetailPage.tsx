import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Dumbbell } from "lucide-react";

import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useExercises } from "@/hooks/useExercises";
import { exercisePhotoSrc } from "@/lib/exercise-photo";
import { PAGE_SHELL_CLASS, PAGE_TITLE_CLASS } from "@/lib/layout";

const LEVEL_LABELS: Record<string, string> = {
  beginner: "Podstawowy",
  intermediate: "Średni",
  advanced: "Zaawansowany",
};

/**
 * `/exercises/:slug` (ADR-14 amendment 2026-08-23) — shared details for the catalog
 * (/settings) and clickable exercise names in plans. Data from `useExercises` cache
 * (staleTime 1 h), so navigation is instant; no separate detail endpoint.
 */
export default function ExerciseDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { data: exercises, isLoading } = useExercises();

  const exercise = exercises?.find((ex) => ex.slug === slug);

  if (isLoading) {
    return (
      <div className={PAGE_SHELL_CLASS}>
        <Skeleton className="h-8 w-64" />
        <Skeleton className="mt-4 aspect-video w-full max-w-xl" />
        <Skeleton className="mt-4 h-24 w-full" />
      </div>
    );
  }

  if (!exercise) {
    return (
      <div className={PAGE_SHELL_CLASS}>
        <Button variant="ghost" size="sm" asChild className="-ml-2 mb-4">
          <Link to="/settings">
            <ArrowLeft className="mr-1 h-4 w-4" /> Wróć
          </Link>
        </Button>
        <h1 className={PAGE_TITLE_CLASS}>Nie znaleziono ćwiczenia</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          To ćwiczenie nie istnieje w katalogu lub nie zostało jeszcze pobrane.
        </p>
      </div>
    );
  }

  const photoSrc = exercisePhotoSrc(exercise.photo_path);
  const photoSrc2 = exercisePhotoSrc(exercise.photo_path_2);

  return (
    <div className={`${PAGE_SHELL_CLASS} max-w-3xl`}>
      <Button variant="ghost" size="sm" asChild className="-ml-2 mb-4">
        <Link to="/settings">
          <ArrowLeft className="mr-1 h-4 w-4" /> Katalog ćwiczeń
        </Link>
      </Button>

      <h1 className={PAGE_TITLE_CLASS}>{exercise.name}</h1>

      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant="outline">{LEVEL_LABELS[exercise.level]}</Badge>
        {exercise.categories.map((category) => (
          <Badge key={category} variant="secondary">
            {category}
          </Badge>
        ))}
      </div>

      {photoSrc || photoSrc2 ? (
        <div
          className={`mt-5 grid gap-3 ${photoSrc && photoSrc2 ? "sm:grid-cols-2" : "grid-cols-1"}`}
        >
          {photoSrc ? (
            <AspectRatio ratio={3 / 2} className="overflow-hidden rounded-md bg-muted">
              <img
                src={photoSrc}
                alt={`${exercise.name} — pozycja startowa`}
                loading="lazy"
                decoding="async"
                className="h-full w-full object-cover"
              />
            </AspectRatio>
          ) : null}
          {photoSrc2 ? (
            <AspectRatio ratio={3 / 2} className="overflow-hidden rounded-md bg-muted">
              <img
                src={photoSrc2}
                alt={`${exercise.name} — pozycja końcowa`}
                loading="lazy"
                decoding="async"
                className="h-full w-full object-cover"
              />
            </AspectRatio>
          ) : null}
        </div>
      ) : (
        <AspectRatio ratio={3 / 2} className="mt-5 overflow-hidden rounded-md bg-muted">
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <Dumbbell className="h-10 w-10" />
          </div>
        </AspectRatio>
      )}

      <p className="mt-5 text-sm text-muted-foreground">{exercise.short_description}</p>

      <Separator className="my-6" />

      <section>
        <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Wykonanie</h2>
        <p className="mt-2 whitespace-pre-line text-sm">{exercise.detail_full}</p>
      </section>

      {exercise.common_mistakes ? (
        <>
          <Separator className="my-6" />
          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Częste błędy</h2>
            <p className="mt-2 text-sm">{exercise.common_mistakes}</p>
          </section>
        </>
      ) : null}
    </div>
  );
}
