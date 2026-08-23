import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Dumbbell } from "lucide-react";

import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useExercises } from "@/hooks/useExercises";
import { PAGE_SHELL_CLASS, PAGE_TITLE_CLASS } from "@/lib/layout";

const LEVEL_LABELS: Record<string, string> = {
  beginner: "Podstawowy",
  intermediate: "Średni",
  advanced: "Zaawansowany",
};

/**
 * `/exercises/:slug` (ADR-14 nowelizacja 2026-08-23) — wspólne szczegóły dla katalogu
 * (/settings) i klikalnych nazw w planach. Dane z cache `useExercises` (staleTime 1 h),
 * więc nawigacja jest natychmiastowa; bez osobnego endpointu detail.
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

      <AspectRatio ratio={3 / 2} className="mt-5 overflow-hidden rounded-md bg-muted">
        {exercise.photo_path ? (
          <img
            src={exercise.photo_path}
            alt={exercise.name}
            loading="lazy"
            decoding="async"
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <Dumbbell className="h-10 w-10" />
          </div>
        )}
      </AspectRatio>

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
