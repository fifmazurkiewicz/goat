import { Dumbbell } from "lucide-react";

import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ResponsiveDialog } from "@/components/common/ResponsiveDialog";
import type { Exercise } from "@/types/api";

interface ExerciseDetailDialogProps {
  exercise: Exercise | null;
  onOpenChange: (open: boolean) => void;
}

const LEVEL_LABELS: Record<Exercise["level"], string> = {
  beginner: "Podstawowy",
  intermediate: "Średni",
  advanced: "Zaawansowany",
};

/** `Sheet` na mobile / `Dialog` desktop (przez `ResponsiveDialog`) — zdjęcie, "Wykonanie", "Częste błędy". */
export function ExerciseDetailDialog({ exercise, onOpenChange }: ExerciseDetailDialogProps) {
  return (
    <ResponsiveDialog
      open={Boolean(exercise)}
      onOpenChange={onOpenChange}
      title={exercise?.name ?? ""}
      className="sm:max-w-xl"
      footer={
        <Button variant="secondary" onClick={() => onOpenChange(false)}>
          Zamknij
        </Button>
      }
    >
      {exercise ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{LEVEL_LABELS[exercise.level]}</Badge>
            {exercise.categories.map((category) => (
              <Badge key={category} variant="secondary">
                {category}
              </Badge>
            ))}
          </div>
          <AspectRatio ratio={16 / 9} className="overflow-hidden rounded-md bg-muted">
            {exercise.photo_path ? (
              <img src={exercise.photo_path} alt={exercise.name} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                <Dumbbell className="h-10 w-10" />
              </div>
            )}
          </AspectRatio>
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Wykonanie</div>
            <p className="mt-1 whitespace-pre-line text-sm">{exercise.detail_full}</p>
          </div>
          <Separator />
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Częste błędy</div>
            <p className="mt-1 text-sm">{exercise.common_mistakes}</p>
          </div>
        </div>
      ) : null}
    </ResponsiveDialog>
  );
}
