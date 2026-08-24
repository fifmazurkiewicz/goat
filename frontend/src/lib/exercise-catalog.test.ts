import { describe, expect, it } from "vitest";

import { pickRandomExercises, visibleExercises } from "@/lib/exercise-catalog";
import type { Exercise } from "@/types/api";

function exercise(slug: string, extra: Partial<Exercise> = {}): Exercise {
  return {
    id: slug,
    slug,
    name: slug.replace(/-/g, " "),
    name_en: slug,
    persona_type: "motor_coach",
    level: "beginner",
    categories: ["Siłowe"],
    short_description: "opis",
    detail_full: "kroki",
    common_mistakes: null,
    photo_path: null,
    ...extra,
  };
}

const catalog = [
  exercise("a"),
  exercise("b"),
  exercise("c"),
  exercise("d"),
  exercise("e"),
];

describe("pickRandomExercises", () => {
  it("zwraca dokładnie N unikalnych pozycji", () => {
    const picked = pickRandomExercises(catalog, 3, () => 0.5);
    expect(picked).toHaveLength(3);
    expect(new Set(picked.map((e) => e.slug)).size).toBe(3);
  });

  it("gdy katalog jest krótszy niż N, zwraca wszystkie", () => {
    expect(pickRandomExercises(catalog.slice(0, 2), 3, () => 0.1)).toHaveLength(2);
  });

  it("kolejne losowania z innym RNG dają inną kolejność/zestaw", () => {
    const first = pickRandomExercises(catalog, 3, () => 0.1).map((e) => e.slug);
    const second = pickRandomExercises(catalog, 3, () => 0.9).map((e) => e.slug);
    expect(first).not.toEqual(second);
  });
});

describe("visibleExercises", () => {
  const sample = [exercise("a"), exercise("b"), exercise("c")];

  it("przy pustym query pokazuje próbkę, nie cały katalog", () => {
    const shown = visibleExercises({
      all: catalog,
      sample,
      query: "",
      category: "all",
    });
    expect(shown.map((e) => e.slug)).toEqual(["a", "b", "c"]);
  });

  it("po wpisaniu słowa filtruje cały katalog (PL/EN)", () => {
    const withEn = [
      ...catalog,
      exercise("przysiad", { name: "Przysiad ze sztangą", name_en: "Barbell Squat" }),
    ];
    const shown = visibleExercises({
      all: withEn,
      sample,
      query: "squat",
      category: "all",
    });
    expect(shown.map((e) => e.slug)).toEqual(["przysiad"]);
  });

  it("kategoria bez query pokazuje próbkę z puli (nie cały katalog)", () => {
    const shown = visibleExercises({
      all: catalog,
      sample: [exercise("uda-1", { categories: ["Uda"] })],
      query: "  ",
      category: "Uda",
    });
    expect(shown.map((e) => e.slug)).toEqual(["uda-1"]);
  });
});
