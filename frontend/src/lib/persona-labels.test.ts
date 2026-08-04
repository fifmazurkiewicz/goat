import { describe, expect, it } from "vitest";

import { formatPersonaDisplayLabel } from "@/lib/persona-labels";

describe("formatPersonaDisplayLabel", () => {
  it("łączy imię z rolą gdy się różnią", () => {
    expect(formatPersonaDisplayLabel("Kasia", "personal_trainer")).toBe("Kasia · Trener personalny");
  });

  it("nie duplikuje gdy imię = rola", () => {
    expect(formatPersonaDisplayLabel("Dietetyk", "dietitian")).toBe("Dietetyk");
  });
});
