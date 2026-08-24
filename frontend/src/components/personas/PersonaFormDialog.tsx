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
import {
  useCreatePersona,
  useDeletePersona,
  usePersonaTemplates,
  usePlanTemplates,
  useUpdatePersona,
} from "@/hooks/usePersonas";
import { ApiError, getErrorMessage } from "@/lib/api-client";
import {
  columnsFromTemplateOverrides,
  templateOverridesFromColumns,
} from "@/lib/persona-template-overrides";
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
 * "Add persona" / edit-prompt dialog — React Hook Form + Zod, sections: basic data /
 * system prompt / day structure (Accordion, advanced). docs/technical/frontend.md
 * section 7. `Sheet` on mobile (§11) via `ResponsiveDialog`. `persona_constraints` is
 * deliberately absent — it's a system field (ai-pipeline.md).
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
  const deletePersona = useDeletePersona();

  const form = useForm<PersonaFormValues>({
    resolver: zodResolver(personaFormSchema),
    defaultValues: {
      base_template_id: persona?.base_template_id ?? "",
      persona_type: persona?.type ?? "",
      name: persona?.name ?? "",
      system_prompt: persona?.system_prompt ?? "",
      detail_level: persona?.detail_level ?? "simple",
      plan_template_id: persona?.plan_template_id ?? null,
      columns: columnsFromTemplateOverrides(persona?.template_overrides),
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
      detail_level: persona?.detail_level ?? "simple",
      plan_template_id: persona?.plan_template_id ?? null,
      columns: columnsFromTemplateOverrides(persona?.template_overrides),
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
    form.setValue("persona_type", template.type, { shouldValidate: true });
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
    if (!isEdit) {
      if (!values.base_template_id.trim()) {
        form.setError("base_template_id", { message: "Wybierz szablon" });
        toast.error("Popraw błędy w formularzu przed zapisem");
        return;
      }
      if (!values.persona_type.trim()) {
        form.setError("persona_type", { message: "Wybierz gotowiec" });
        toast.error("Popraw błędy w formularzu przed zapisem");
        return;
      }
    }

    const templateOverrides = templateOverridesFromColumns(values.columns);
    if (templateOverrides.columns.length === 0) {
      form.setError("columns", { message: "Dodaj przynajmniej jedną kolumnę" });
      toast.error("Popraw błędy w formularzu przed zapisem");
      return;
    }

    try {
      if (isEdit && persona) {
        await updatePersona.mutateAsync({
          id: persona.id,
          input: {
            name: values.name,
            system_prompt: values.system_prompt,
            detail_level: values.detail_level,
            template_overrides: templateOverrides,
            plan_template_id: values.plan_template_id,
            custom_result_category: values.custom_result_category,
          },
        });
        toast.success("Zapisano zmiany persony");
      } else {
        await createPersona.mutateAsync({
          base_template_id: values.base_template_id,
          type: values.persona_type as Persona["type"],
          name: values.name,
          system_prompt: values.system_prompt,
          detail_level: values.detail_level,
          plan_template_id: values.plan_template_id,
          template_overrides: templateOverrides,
          custom_result_category: values.custom_result_category,
        });
        toast.success("Dodano nową personę");
      }
      onOpenChange(false);
    } catch (err) {
      toast.error(getErrorMessage(err, "Nie udało się zapisać persony. Spróbuj ponownie."));
    }
  }

  function onInvalid() {
    toast.error("Popraw błędy w formularzu przed zapisem");
  }

  async function handleDelete() {
    if (!persona) return;
    const confirmed = window.confirm(
      `Usunąć personę „${persona.name}”? Tej operacji nie można cofnąć.`
    );
    if (!confirmed) return;
    try {
      await deletePersona.mutateAsync(persona.id);
      toast.success("Usunięto personę");
      onOpenChange(false);
    } catch (err) {
      toast.error(getErrorMessage(err, "Nie udało się usunąć persony."));
    }
  }

  const isPending =
    createPersona.isPending || updatePersona.isPending || deletePersona.isPending;

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
        <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
          {isEdit ? (
            <Button
              type="button"
              variant="destructive"
              onClick={() => void handleDelete()}
              disabled={isPending}
            >
              {deletePersona.isPending ? "Usuwanie…" : "Usuń personę"}
            </Button>
          ) : (
            <span />
          )}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              Anuluj
            </Button>
            <Button type="submit" form="persona-form" disabled={isPending}>
              {isPending && !deletePersona.isPending
                ? "Zapisywanie…"
                : isEdit
                  ? "Zapisz zmiany"
                  : "Dodaj personę"}
            </Button>
          </div>
        </div>
      }
    >
      <FormProvider {...form}>
        <form id="persona-form" onSubmit={form.handleSubmit(onSubmit, onInvalid)} className="space-y-5">
          {!isEdit && (
            <div className="space-y-2">
              <Label htmlFor="persona-template">Wybierz gotowiec</Label>
              {templatesLoading ? (
                <Skeleton
                  className="h-10 w-full"
                  role="status"
                  aria-live="polite"
                  aria-label="Ładowanie gotowców"
                />
              ) : templatesError ? (
                <p className="text-sm text-destructive" role="alert">
                  {templatesQueryError instanceof ApiError
                    ? templatesQueryError.message
                    : "Nie udało się wczytać gotowców. Spróbuj ponownie."}
                </p>
              ) : !templates?.length ? (
                <p className="text-sm text-muted-foreground">Brak gotowców</p>
              ) : (
                <Select
                  value={selectedTemplateId || undefined}
                  onValueChange={handleTemplateSelect}
                >
                  <SelectTrigger id="persona-template" aria-invalid={Boolean(form.formState.errors.base_template_id)}>
                    <SelectValue placeholder="Wybierz gotowiec" />
                  </SelectTrigger>
                  <SelectContent>
                    {templates.map((template) => (
                      <SelectItem key={template.id} value={template.id}>
                        {template.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              {form.formState.errors.base_template_id ? (
                <p className="text-sm text-destructive">{form.formState.errors.base_template_id.message}</p>
              ) : null}
              {form.formState.errors.persona_type ? (
                <p className="text-sm text-destructive">{form.formState.errors.persona_type.message}</p>
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
              <Label htmlFor="persona-prompt">Styl i zakres pomocy</Label>
              <span className="text-xs text-muted-foreground">
                {systemPromptValue.length}/{SYSTEM_PROMPT_MAX_LENGTH}
              </span>
            </div>
            <Textarea
              id="persona-prompt"
              rows={6}
              className="min-h-[140px]"
              maxLength={SYSTEM_PROMPT_MAX_LENGTH}
              placeholder="Ton rozmowy, w czym ma pomagać, jak współpracować z innymi personami…"
              {...form.register("system_prompt")}
            />
            <p className="text-xs text-muted-foreground">
              Zasady bezpieczeństwa aplikacji działają zawsze — niezależnie od tego, co tu wpiszesz.
            </p>
            {form.formState.errors.system_prompt ? (
              <p className="text-sm text-destructive">{form.formState.errors.system_prompt.message}</p>
            ) : null}
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
