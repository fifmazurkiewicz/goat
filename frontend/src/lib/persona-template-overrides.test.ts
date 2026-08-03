import { describe, expect, it } from "vitest";

import {
  columnsFromTemplateOverrides,
  templateOverridesFromColumns,
} from "@/lib/persona-template-overrides";

describe("persona-template-overrides", () => {
  it("mapuje API { columns } na draft formularza", () => {
    expect(columnsFromTemplateOverrides({ columns: ["Posiłek", "Kcal"] })).toEqual([
      { name: "Posiłek" },
      { name: "Kcal" },
    ]);
  });

  it("mapuje draft formularza na kontrakt API", () => {
    expect(
      templateOverridesFromColumns([{ name: "  Posiłek " }, { name: "Kcal" }, { name: "  " }])
    ).toEqual({ columns: ["Posiłek", "Kcal"] });
  });

  it("toleruje legacy tablicę { name }", () => {
    expect(columnsFromTemplateOverrides([{ name: "Serie" }])).toEqual([{ name: "Serie" }]);
  });

  it("zwraca domyślną kolumnę dla pustego overrides", () => {
    expect(columnsFromTemplateOverrides(null)).toEqual([{ name: "Kolumna 1" }]);
  });
});
