import { describe, expect, it } from "vitest";

import { buildDetailsFromInputs } from "@/lib/result-details-form";

describe("buildDetailsFromInputs", () => {
  it("keeps filled columns in order and returns the exercise cell", () => {
    expect(buildDetailsFromInputs(["Ćwiczenie", "Serie", "Ciężar (kg)"], ["Dead bug ", "", "50 / stronę"])).toEqual({
      details: [
        { label: "Ćwiczenie", value: "Dead bug" },
        { label: "Ciężar (kg)", value: "50 / stronę" },
      ],
      exercise: "Dead bug",
    });
  });

  it("returns null details when nothing is filled", () => {
    expect(buildDetailsFromInputs(["Ćwiczenie"], ["  "])).toEqual({ details: null, exercise: "" });
  });
});
