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
import { Textarea } from "@/components/ui/textarea";
import { useCreateResult } from "@/hooks/useResults";
import { getErrorMessage } from "@/lib/api-client";
import type { ResultCategory } from "@/types/api";

const schema = z.object({
  metric: z.string().trim().min(1, "Podaj nazwę metryki"),
  value: z.coerce.number().finite("Podaj liczbę"),
  unit: z.string().trim().min(1, "Podaj jednostkę"),
  logged_date: z.string().min(1, "Podaj datę"),
  notes: z.string().trim().optional(),
});

type FormValues = z.infer<typeof schema>;

interface AddResultDialogProps {
  category: ResultCategory;
}

export function AddResultDialog({ category }: AddResultDialogProps) {
  const [open, setOpen] = useState(false);
  const createResult = useCreateResult();
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { metric: "", value: 0, unit: "", logged_date: format(new Date(), "yyyy-MM-dd"), notes: "" },
  });

  async function onSubmit(values: FormValues) {
    try {
      await createResult.mutateAsync({ ...values, category, notes: values.notes || null });
      toast.success("Dodano wynik");
      form.reset({ metric: "", value: 0, unit: "", logged_date: format(new Date(), "yyyy-MM-dd"), notes: "" });
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
          <div className="space-y-1.5">
            <Label htmlFor="metric">Metryka</Label>
            <Input id="metric" placeholder="np. bench_press_1rm" {...form.register("metric")} />
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
