import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { format } from "date-fns";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ResponsiveDialog } from "@/components/common/ResponsiveDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateResult } from "@/hooks/useResults";
import { getErrorMessage } from "@/lib/api-client";
import { buildDetailsFromInputs } from "@/lib/result-details-form";
import type { Persona, ResultCategory } from "@/types/api";

const schema = z.object({
  // Required unless the persona's exercise column is filled (checked in onSubmit).
  metric: z.string().trim(),
  value: z.coerce.number().finite("Podaj liczbę"),
  unit: z.string().trim().min(1, "Podaj jednostkę"),
  logged_date: z.string().min(1, "Podaj datę"),
  notes: z.string().trim().optional(),
});

type FormValues = z.infer<typeof schema>;

interface AddResultDialogProps {
  category: ResultCategory;
  /** Personas of this category with plan columns (ADR-25) — their columns become `details` inputs. */
  personas?: Persona[];
}

export function AddResultDialog({ category, personas = [] }: AddResultDialogProps) {
  const [open, setOpen] = useState(false);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [columnValues, setColumnValues] = useState<string[]>([]);
  const persona = personas.find((p) => p.id === personaId) ?? personas[0] ?? null;
  const columns = persona?.plan_columns ?? [];
  const createResult = useCreateResult();
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { metric: "", value: 0, unit: "", logged_date: format(new Date(), "yyyy-MM-dd"), notes: "" },
  });

  async function onSubmit(values: FormValues) {
    const { details, exercise } = buildDetailsFromInputs(columns, columnValues);
    const metric = values.metric || exercise;
    if (!metric) {
      form.setError("metric", { message: "Podaj nazwę metryki lub ćwiczenia" });
      return;
    }
    try {
      await createResult.mutateAsync({ ...values, metric, category, notes: values.notes || null, details });
      toast.success("Dodano wynik");
      form.reset({ metric: "", value: 0, unit: "", logged_date: format(new Date(), "yyyy-MM-dd"), notes: "" });
      setColumnValues([]);
      setOpen(false);
    } catch (err) {
      toast.error(getErrorMessage(err, "Nie udało się dodać wyniku."));
    }
  }

  return (
    <>
      <Button type="button" onClick={() => setOpen(true)}>
        Dodaj wynik ręcznie
      </Button>
      <ResponsiveDialog
        open={open}
        onOpenChange={setOpen}
        title="Dodaj wynik ręcznie"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Anuluj
            </Button>
            <Button type="submit" form="add-result-form" disabled={createResult.isPending}>
              Dodaj
            </Button>
          </>
        }
      >
        <form id="add-result-form" onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
          {personas.length > 1 ? (
            <div className="space-y-1.5">
              <Label htmlFor="result-persona">Persona</Label>
              <Select
                value={persona?.id}
                onValueChange={(id) => {
                  setPersonaId(id);
                  setColumnValues([]);
                }}
              >
                <SelectTrigger id="result-persona">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {personas.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
          {columns.length > 0 ? (
            <fieldset className="grid gap-3 sm:grid-cols-2">
              <legend className="mb-1.5 text-sm font-medium">Szczegóły (kolumny planu)</legend>
              {columns.map((column, index) => (
                <div key={column} className="space-y-1.5">
                  <Label htmlFor={`detail-${index}`}>{column}</Label>
                  <Input
                    id={`detail-${index}`}
                    value={columnValues[index] ?? ""}
                    onChange={(event) => {
                      const next = [...columnValues];
                      next[index] = event.target.value;
                      setColumnValues(next);
                    }}
                  />
                </div>
              ))}
            </fieldset>
          ) : null}
          <div className="space-y-1.5">
            <Label htmlFor="metric">Metryka</Label>
            <Input
              id="metric"
              placeholder={columns.length > 0 ? "domyślnie: nazwa ćwiczenia" : "np. bench_press_1rm"}
              {...form.register("metric")}
            />
            {form.formState.errors.metric ? (
              <p className="text-sm text-destructive">{form.formState.errors.metric.message}</p>
            ) : null}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="value">Wartość</Label>
              <Input id="value" type="number" step="any" {...form.register("value")} />
              {form.formState.errors.value ? (
                <p className="text-sm text-destructive">{form.formState.errors.value.message}</p>
              ) : null}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="unit">Jednostka</Label>
              <Input id="unit" placeholder="kg / s / g" {...form.register("unit")} />
              {form.formState.errors.unit ? (
                <p className="text-sm text-destructive">{form.formState.errors.unit.message}</p>
              ) : null}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="logged_date">Data</Label>
            <Input id="logged_date" type="date" {...form.register("logged_date")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="notes">Notatki</Label>
            <Textarea id="notes" rows={2} {...form.register("notes")} />
          </div>
        </form>
      </ResponsiveDialog>
    </>
  );
}
