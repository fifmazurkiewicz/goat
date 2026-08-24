import { describe, expect, it } from "vitest";

import { formatPersonaDisplayLabel } from "@/lib/persona-labels";

describe("formatPersonaDisplayLabel", () => {
  it("combines the name with the role when they differ", () => {
    expect(formatPersonaDisplayLabel("Kasia", "personal_trainer")).toBe("Kasia · Trener personalny");
  });

  it("does not duplicate when name = role", () => {
    expect(formatPersonaDisplayLabel("Dietetyk", "dietitian")).toBe("Dietetyk");
  });
});
