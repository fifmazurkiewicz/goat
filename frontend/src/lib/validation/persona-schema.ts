import { z } from "zod";

// React Hook Form + Zod (zodResolver) — docs/technical/frontend.md sekcja 7.
// Edytor kolumn (`template_overrides`): min. 1 kolumna, max ~8, unikalne nazwy,
// `custom_result_category` wymagane warunkowo (`superRefine`) dla `type==='custom'`.
// `persona_constraints` NIE jest w formularzu (pole systemowe — ai-pipeline.md).
// `base_template_id` wymagany przy create — walidacja w submit (edycja może mieć null).

export const personaColumnSchema = z.object({
  name: z.string().trim().min(1, "Nazwa kolumny jest wymagana").max(40, "Maks. 40 znaków"),
});

export const personaFormSchema = z
  .object({
    base_template_id: z.string(),
    persona_type: z.string().min(1, "Wybierz gotowiec"),
    name: z.string().trim().min(2, "Nazwa musi mieć min. 2 znaki").max(60, "Maks. 60 znaków"),
    system_prompt: z
      .string()
      .trim()
      .min(20, "Opisz personę dokładniej (min. 20 znaków)")
      .max(4000, "Maks. 4000 znaków"),
    detail_level: z.enum(["simple", "detailed"]),
    plan_template_id: z.string().nullable().default(null),
    columns: z
      .array(personaColumnSchema)
      .min(1, "Dodaj przynajmniej jedną kolumnę")
      .max(8, "Maksymalnie 8 kolumn"),
    custom_result_category: z.string().trim().max(60).nullable().default(null),
  })
  .superRefine((data, ctx) => {
    const normalized = data.columns.map((c) => c.name.trim().toLowerCase());
    const hasDuplicates = new Set(normalized).size !== normalized.length;
    if (hasDuplicates) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Nazwy kolumn muszą być unikalne",
        path: ["columns"],
      });
    }

    if (data.persona_type === "custom" && !data.custom_result_category?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Podaj kategorię wyników dla persony typu custom",
        path: ["custom_result_category"],
      });
    }
  });

export type PersonaFormValues = z.infer<typeof personaFormSchema>;

export const SYSTEM_PROMPT_MAX_LENGTH = 4000;
