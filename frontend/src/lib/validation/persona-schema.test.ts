import { describe, expect, it } from "vitest";

import { personaFormSchema } from "@/lib/validation/persona-schema";

function buildValidInput(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    base_template_id: "template-1",
    persona_type: "personal_trainer",
    name: "Trener Kasia",
    system_prompt: "Jesteś doświadczonym trenerem personalnym specjalizującym się w sile.",
    detail_level: "simple",
    plan_template_id: null,
    columns: [{ name: "Ćwiczenie" }, { name: "Serie" }],
    custom_result_category: null,
    ...overrides,
  };
}

describe("personaFormSchema", () => {
  it("accepts valid data", () => {
    const result = personaFormSchema.safeParse(buildValidInput());
    expect(result.success).toBe(true);
  });

  it("rejects a name that is too short", () => {
    const result = personaFormSchema.safeParse(buildValidInput({ name: "A" }));
    expect(result.success).toBe(false);
  });

  it("rejects a system prompt that is too short", () => {
    const result = personaFormSchema.safeParse(buildValidInput({ system_prompt: "Za krótko" }));
    expect(result.success).toBe(false);
  });

  it("requires at least one column", () => {
    const result = personaFormSchema.safeParse(buildValidInput({ columns: [] }));
    expect(result.success).toBe(false);
  });

  it("rejects more than 8 columns", () => {
    const columns = Array.from({ length: 9 }, (_, i) => ({ name: `Kolumna ${i}` }));
    const result = personaFormSchema.safeParse(buildValidInput({ columns }));
    expect(result.success).toBe(false);
  });

  it("rejects duplicate column names (case-insensitive)", () => {
    const result = personaFormSchema.safeParse(
      buildValidInput({ columns: [{ name: "Ćwiczenie" }, { name: "ćwiczenie" }] })
    );
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((issue) => issue.path.includes("columns"))).toBe(true);
    }
  });

  it("requires custom_result_category when persona_type === 'custom'", () => {
    const result = personaFormSchema.safeParse(
      buildValidInput({ persona_type: "custom", custom_result_category: null })
    );
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((issue) => issue.path.includes("custom_result_category"))).toBe(true);
    }
  });

  it("accepts persona_type === 'custom' with a provided category", () => {
    const result = personaFormSchema.safeParse(
      buildValidInput({ persona_type: "custom", custom_result_category: "Wspinaczka" })
    );
    expect(result.success).toBe(true);
  });
});
