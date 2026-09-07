import { describe, expect, it } from "vitest";

import {
  buildExerciseMatcher,
  findExerciseColumnIndex,
} from "@/lib/exercise-matcher";
import type { Exercise } from "@/types/api";

function exercise(partial: Partial<Exercise> & Pick<Exercise, "slug" | "name">): Exercise {
  return {
    id: partial.slug,
    name_en: partial.name_en ?? partial.name,
    persona_type: "motor_coach",
    level: "beginner",
    categories: ["Siłowe"],
    short_description: "opis",
    detail_full: "kroki",
    common_mistakes: null,
    photo_path: null,
    ...partial,
  };
}

describe("findExerciseColumnIndex", () => {
  it("returns the Ćwiczenie column when Day is first (motor_coach layout)", () => {
    expect(
      findExerciseColumnIndex(["Dzień (P/P/L)", "Ćwiczenie", "Serie", "Powtórzenia"])
    ).toBe(1);
  });

  it("matches English Exercise header", () => {
    expect(findExerciseColumnIndex(["Day", "Exercise", "Sets"])).toBe(1);
  });

  it("falls back to column 0 when no exercise header exists", () => {
    expect(findExerciseColumnIndex(["Nazwa", "Serie"])).toBe(0);
  });

  it("returns 0 when Ćwiczenie is already first", () => {
    expect(findExerciseColumnIndex(["Ćwiczenie", "Serie"])).toBe(0);
  });
});

describe("buildExerciseMatcher", () => {
  const catalog = [
    exercise({ slug: "calf-raise", name: "Wspięcia na palce", name_en: "Calf Raise" }),
    exercise({
      slug: "kettlebell-swing",
      name: "Swing kettlebell",
      name_en: "Kettlebell Swing",
    }),
    exercise({
      slug: "pallof-press",
      name: "Pallof press",
      name_en: "Pallof Press",
    }),
  ];

  it("matches a plain EN name", () => {
    const match = buildExerciseMatcher(catalog);
    expect(match("Calf Raise")?.slug).toBe("calf-raise");
  });

  it("matches the second alternative after LUB", () => {
    const match = buildExerciseMatcher(catalog);
    expect(
      match("Trap bar / KB jump shrug LUB kettlebell swing (hip hinge)")?.slug
    ).toBe("kettlebell-swing");
  });

  it("matches when a parenthetical gloss follows the name", () => {
    const match = buildExerciseMatcher(catalog);
    expect(match("Pallof press anti-rotacja")?.slug).toBe("pallof-press");
  });

  it("matches when extra tokens interrupt the name order (bag of words)", () => {
    const match = buildExerciseMatcher(catalog);
    expect(match("Calf raise 2-leg (pełny ROM, kontrola)")?.slug).toBe("calf-raise");
  });
});
