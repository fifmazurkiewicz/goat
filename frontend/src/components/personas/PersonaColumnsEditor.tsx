import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";
import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { PersonaFormValues } from "@/lib/validation/persona-schema";

const MAX_COLUMNS = 8;

/**
 * `template_overrides` — lista edytowalna przez `useFieldArray` (nazwa kolumny + ↑/↓
 * reorder + usuń + "+ Dodaj kolumnę"), bez drag-n-drop na MVP (docs/technical/frontend.md
 * sekcja 7).
 */
export function PersonaColumnsEditor() {
  const {
    control,
    register,
    formState: { errors },
  } = useFormContext<PersonaFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "columns" });

  const columnsError = errors.columns?.message ?? errors.columns?.root?.message;

  return (
    <div className="space-y-2">
      <Label>Kolumny rozpiski</Label>
      <div className="space-y-2">
        {fields.map((field, index) => (
          <div key={field.id} className="flex items-center gap-2">
            <Input
              {...register(`columns.${index}.name` as const)}
              aria-label={`Nazwa kolumny ${index + 1}`}
              placeholder="np. Ćwiczenie"
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              disabled={index === 0}
              onClick={() => move(index, index - 1)}
              aria-label="Przesuń wyżej"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              disabled={index === fields.length - 1}
              onClick={() => move(index, index + 1)}
              aria-label="Przesuń niżej"
            >
              <ArrowDown className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={fields.length <= 1}
              onClick={() => remove(index)}
              aria-label="Usuń kolumnę"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </div>
      {typeof columnsError === "string" ? <p className="text-sm text-destructive">{columnsError}</p> : null}
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={fields.length >= MAX_COLUMNS}
        onClick={() => append({ name: "" })}
      >
        <Plus className="mr-1 h-4 w-4" /> Dodaj kolumnę
      </Button>
    </div>
  );
}
