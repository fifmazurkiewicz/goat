import { useEffect, useMemo } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { FormProvider, useForm } from "react-hook-form";
import { toast } from "sonner";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ResponsiveDialog } from "@/components/common/ResponsiveDialog";
import { PersonaColumnsEditor } from "@/components/personas/PersonaColumnsEditor";
import { useCreatePersona, usePersonaTemplates, usePlanTemplates, useUpdatePersona } from "@/hooks/usePersonas";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { personaFormSchema, SYSTEM_PROMPT_MAX_LENGTH, type PersonaFormValues } from "@/lib/validation/persona-schema";
import type { Persona } from "@/types/api";

interface PersonaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  persona?: Persona;
}

const DETAIL_LEVEL_OPTIONS: { value: PersonaFormValues["detail_level"]; label: string }[] = [
  { value: "simple", label: "Prosty" },
  { value: "detailed", label: "Szczegółowy" },
];

/**
 * Dialog "Dodaj personę" / edycja promptu — React Hook Form + Zod, sekcje: podstawowe
 * dane / system prompt / persona_constraints / struktura dnia (Accordion, zaawansowane).
 * docs/technical/frontend.md sekcja 7. `Sheet` na mobile (§11) przez `ResponsiveDialog`.
 */
export function PersonaFormDialog({ open, onOpenChange, persona }: PersonaFormDialogProps) {
  const isEdit = Boolean(persona);
  const {
    data: templates,
    isLoading: templatesLoading,
    isError: templatesError,
    error: templatesQueryError,
  } = usePersonaTemplates();
  const { data: planTemplates } = usePlanTemplates();
  const createPersona = useCreatePersona();
  const updatePersona = useUpdatePersona();

  const form = useForm<PersonaFormValues>({
    resolver: zodResolver(personaFormSchema),
    defaultValues: {
      base_template_id: persona?.base_template_id ?? "",
      persona_type: persona?.type ?? "",
      name: persona?.name ?? "",
      system_prompt: persona?.system_prompt ?? "",
      persona_constraints: persona?.persona_constraints ?? "",
      detail_level: persona?.detail_level ?? "simple",
      plan_template_id: persona?.plan_template_id ?? null,
      columns: persona?.template_overrides?.length
        ? persona.template_overrides
        : [{ name: "Kolumna 1" }],
      custom_result_category: persona?.custom_result_category ?? null,
    },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      base_template_id: persona?.base_template_id ?? "",
      persona_type: persona?.type ?? "",
      name: persona?.name ?? "",
      system_prompt: persona?.system_prompt ?? "",
      persona_constraints: persona?.persona_constraints ?? "",
      detail_level: persona?.detail_level ?? "simple",
      plan_template_id: persona?.plan_template_id ?? null,
      columns: persona?.template_overrides?.length ? persona.template_overrides : [{ name: "Kolumna 1" }],
      custom_result_category: persona?.custom_result_category ?? null,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, persona]);

  const selectedTemplateId = form.watch("base_template_id");
  const selectedPlanTemplateId = form.watch("plan_template_id");
  const personaType = form.watch("persona_type");
  const systemPromptValue = form.watch("system_prompt") ?? "";

  const suggestedPlanTemplates = useMemo(() => {
    if (!planTemplates) return [];
    if (!personaType) return planTemplates;
    const suggested = planTemplates.filter((t) => t.suggested_for.includes(personaType));
    return suggested.length > 0 ? suggested : planTemplates;
  }, [planTemplates, personaType]);

  function handleTemplateSelect(templateId: string) {
    const template = templates?.find((t) => t.id === templateId);
    if (!template) return;
    form.setValue("base_template_id", templateId, { shouldValidate: true });
    form.setValue("persona_type", template.type);
    form.setValue("name", template.label);
    if (!isEdit) {
      form.setValue("system_prompt", template.default_prompt, { shouldValidate: true });
    }
  }

  function handlePlanTemplateSelect(planTemplateId: string) {
    form.setValue("plan_template_id", planTemplateId);
    const template = planTemplates?.find((t) => t.id === planTemplateId);
    if (template?.default_columns?.length) {
      form.setValue(
        "columns",
        template.default_columns.map((name) => ({ name }))
      );
    }
  }

  async function onSubmit(values: PersonaFormValues) {
    try {
      if (isEdit && persona) {
        await updatePersona.mutateAsync({
          id: persona.id,
          input: {
            name: values.name,
            system_prompt: values.system_prompt,
            persona_constraints: values.persona_constraints || null,
            detail_level: values.detail_level,
            template_overrides: values.columns,
            plan_template_id: values.plan_template_id,
            custom_result_category: values.custom_result_category,
          },
        });
        toast.success("Zapisano zmiany persony");
      } else {
        await createPersona.mutateAsync({
          base_template_id: values.base_template_id,
          // Backend wymaga `type` — bierzemy z wybranego gotowca (form.persona_type).
          type: values.persona_type as Persona["type"],
          name: values.name,
          system_prompt: values.system_prompt,
          detail_level: values.detail_level,
          plan_template_id: values.plan_template_id,
          custom_result_category: values.custom_result_category,
        });
        toast.success("Dodano nową personę");
      }
      onOpenChange(false);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Nie udało się zapisać persony. Spróbuj ponownie.";
      toast.error(message);
    }
  }

  const isPending = createPersona.isPending || updatePersona.isPending;

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title={isEdit ? `Edytuj personę: ${persona?.name}` : "Dodaj personę"}
      description={
        isEdit
          ? "Zmiany wymagają ponownej weryfikacji moderacji, jeśli persona jest udostępniona."
          : "Wybierz gotowiec, nadaj imię i opisz, jak persona ma się zachowywać."
      }
      className="sm:max-w-2xl"
      footer={
        <>
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Anuluj
          </Button>
          <Button type="submit" form="persona-form" disabled={isPending}>
            {isPending ? "Zapisywanie…" : isEdit ? "Zapisz zmiany" : "Dodaj personę"}
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form id="persona-form" onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
          {!isEdit && (
            <div className="space-y-2">
              <Label id="template-label">Wybierz gotowiec</Label>
              {templatesLoading ? (
                <div
                  role="status"
                  aria-live="polite"
                  aria-label="Ładowanie gotowców"
                  className="grid grid-cols-1 gap-2 sm:grid-cols-2"
                >
                  {[0, 1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : templatesError ? (
                <p className="text-sm text-destructive" role="alert">
                  {templatesQueryError instanceof ApiError
                    ? templatesQueryError.message
                    : "Nie udało się wczytać gotowców. Spróbuj ponownie."}
                </p>
              ) : !templates?.length ? (
                <p className="text-sm text-muted-foreground">Brak gotowców</p>
              ) : (
                <div
                  role="radiogroup"
                  aria-labelledby="template-label"
                  className="grid grid-cols-1 gap-2 sm:grid-cols-2"
                >
                  {templates.map((template) => (
                    <label
                      key={template.id}
                      className={cn(
                        "flex cursor-pointer items-center gap-2 rounded-md border p-3 text-sm transition-colors hover:bg-accent",
                        selectedTemplateId === template.id && "border-primary bg-accent"
                      )}
                    >
                      <input
                        type="radio"
                        name="base_template_id"
                        className="h-4 w-4"
                        checked={selectedTemplateId === template.id}
                        onChange={() => handleTemplateSelect(template.id)}
                      />
                      {template.label}
                    </label>
                  ))}
                </div>
              )}
              {form.formState.errors.base_template_id ? (
                <p className="text-sm text-destructive">{form.formState.errors.base_template_id.message}</p>
              ) : null}
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="persona-name">Nazwa persony</Label>
            <Input id="persona-name" {...form.register("name")} />
            {form.formState.errors.name ? (
              <p className="text-sm text-destructive">{form.formState.errors.name.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="persona-prompt">System prompt (edytowalna część)</Label>
              <span className="text-xs text-muted-foreground">
                {systemPromptValue.length}/{SYSTEM_PROMPT_MAX_LENGTH}
              </span>
            </div>
            <Textarea
              id="persona-prompt"
              rows={6}
              className="min-h-[140px]"
              maxLength={SYSTEM_PROMPT_MAX_LENGTH}
              {...form.register("system_prompt")}
            />
            {form.formState.errors.system_prompt ? (
              <p className="text-sm text-destructive">{form.formState.errors.system_prompt.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="persona-constraints">Twarde ograniczenia (np. kontuzje)</Label>
            <Textarea
              id="persona-constraints"
              rows={2}
              placeholder="np. uraz kolana — unikać przysiadów pełnych"
              {...form.register("persona_constraints")}
            />
          </div>

          <div className="space-y-2">
            <Label id="detail-level-label">Poziom szczegółowości</Label>
            <div role="radiogroup" aria-labelledby="detail-level-label" className="inline-flex rounded-md border p-1">
              {DETAIL_LEVEL_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={cn(
                    "cursor-pointer rounded-sm px-3 py-1.5 text-sm transition-colors",
                    form.watch("detail_level") === option.value
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent"
                  )}
                >
                  <input
                    type="radio"
                    className="sr-only"
                    checked={form.watch("detail_level") === option.value}
                    onChange={() => form.setValue("detail_level", option.value)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </div>

          {personaType === "custom" && (
            <div className="space-y-2">
              <Label htmlFor="custom-category">Kategoria wyników (custom)</Label>
              <Input
                id="custom-category"
                placeholder="np. climbing"
                {...form.register("custom_result_category")}
              />
              {form.formState.errors.custom_result_category ? (
                <p className="text-sm text-destructive">{form.formState.errors.custom_result_category.message}</p>
              ) : null}
            </div>
          )}

          <Accordion type="single" collapsible>
            <AccordionItem value="advanced">
              <AccordionTrigger>Struktura dnia (zaawansowane)</AccordionTrigger>
              <AccordionContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Gotowiec struktury dnia</Label>
                  <Select value={selectedPlanTemplateId ?? undefined} onValueChange={handlePlanTemplateSelect}>
                    <SelectTrigger>
                      <SelectValue placeholder="Wybierz gotowiec (opcjonalnie)" />
                    </SelectTrigger>
                    <SelectContent>
                      {suggestedPlanTemplates.map((template) => (
                        <SelectItem key={template.id} value={template.id}>
                          {template.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <PersonaColumnsEditor />
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </form>
      </FormProvider>
    </ResponsiveDialog>
  );
}
