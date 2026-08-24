import { describe, expect, it } from "vitest";

import { resultCategoryTabsFromPersonas } from "@/lib/result-categories";
import type { Persona } from "@/types/api";

function persona(overrides: Partial<Persona> & Pick<Persona, "id" | "type">): Persona {
  return {
    user_id: "u1",
    name: "P",
    system_prompt: "x".repeat(20),
    base_template_id: null,
    plan_template_id: null,
    template_overrides: null,
    detail_level: "simple",
    custom_result_category: null,
    slug: "p",
    is_shared: false,
    moderation_status: "approved",
    cloned_from_persona_id: null,
    active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("resultCategoryTabsFromPersonas", () => {
  it("builds tabs from persona types only (no triathlon/badminton when missing)", () => {
    const tabs = resultCategoryTabsFromPersonas([
      persona({ id: "1", type: "dietitian" }),
      persona({ id: "2", type: "personal_trainer" }),
    ]);
    expect(tabs.map((t) => t.key)).toEqual(["strength", "diet"]);
  });

  it("prefers only active personas", () => {
    const tabs = resultCategoryTabsFromPersonas([
      persona({ id: "1", type: "badminton_coach", active: false }),
      persona({ id: "2", type: "dietitian", active: true }),
    ]);
    expect(tabs.map((t) => t.key)).toEqual(["diet"]);
  });

  it("deduplicates strength from personal trainer and motor coach", () => {
    const tabs = resultCategoryTabsFromPersonas([
      persona({ id: "1", type: "personal_trainer" }),
      persona({ id: "2", type: "motor_coach" }),
    ]);
    expect(tabs).toEqual([{ key: "strength", label: "Trening" }]);
  });

  it("appends categories from already saved results (outside personas)", () => {
    const tabs = resultCategoryTabsFromPersonas([persona({ id: "1", type: "motor_coach" })], {
      categoriesWithData: ["triathlon", "strength"],
    });
    expect(tabs.map((t) => t.key)).toEqual(["strength", "triathlon"]);
  });

  it("handles custom_result_category", () => {
    const tabs = resultCategoryTabsFromPersonas([
      persona({ id: "1", type: "custom", custom_result_category: "Wspinaczka" }),
    ]);
    expect(tabs).toEqual([{ key: "custom", label: "Wspinaczka" }]);
  });
});
