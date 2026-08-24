import { describe, expect, it } from "vitest";

import {
  columnsFromTemplateOverrides,
  templateOverridesFromColumns,
} from "@/lib/persona-template-overrides";

describe("persona-template-overrides", () => {
  it("maps API { columns } to a form draft", () => {
    expect(columnsFromTemplateOverrides({ columns: ["Posiłek", "Kcal"] })).toEqual([
      { name: "Posiłek" },
      { name: "Kcal" },
    ]);
  });

  it("maps a form draft to the API contract", () => {
    expect(
      templateOverridesFromColumns([{ name: "  Posiłek " }, { name: "Kcal" }, { name: "  " }])
    ).toEqual({ columns: ["Posiłek", "Kcal"] });
  });

  it("tolerates a legacy { name } array", () => {
    expect(columnsFromTemplateOverrides([{ name: "Serie" }])).toEqual([{ name: "Serie" }]);
  });

  it("returns a default column for empty overrides", () => {
    expect(columnsFromTemplateOverrides(null)).toEqual([{ name: "Kolumna 1" }]);
  });
});
