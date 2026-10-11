import { describe, expect, it } from "vitest";

import { buildTrainingSessions, sessionPersonasForCategory } from "@/lib/training-sessions";
import type { Persona, Result } from "@/types/api";

function result(overrides: Partial<Result>): Result {
  return {
    id: "r",
    user_id: "u1",
    category: "strength",
    metric: "Dead bug",
    value: 50,
    unit: "kg",
    logged_date: "2026-10-11",
    source: "agent",
    source_persona_id: "p1",
    is_custom: true,
    notes: null,
    details: null,
    created_at: "2026-10-11T10:00:00Z",
    ...overrides,
  };
}

describe("buildTrainingSessions", () => {
  it("groups by day, newest day first, entries in logging order", () => {
    const sessions = buildTrainingSessions([
      result({ id: "a", logged_date: "2026-10-10" }),
      result({ id: "c", created_at: "2026-10-11T12:00:00Z" }),
      result({ id: "b", created_at: "2026-10-11T09:00:00Z" }),
    ]);
    expect(sessions.map((s) => s.date)).toEqual(["2026-10-11", "2026-10-10"]);
    expect(sessions[0].results.map((r) => r.id)).toEqual(["b", "c"]);
  });

  it("builds one table with the union of labels; legacy rows fall back to Ćwiczenie + Wynik", () => {
    const [session] = buildTrainingSessions([
      result({ id: "a", details: [{ label: "Ćwiczenie", value: "Dead bug" }, { label: "Serie", value: "3" }] }),
      result({ id: "b", metric: "weight_kg", value: 82.5, unit: "kg", details: null, created_at: "2026-10-11T11:00:00Z" }),
    ]);
    expect(session.content.columns).toEqual(["Ćwiczenie", "Serie", "Wynik"]);
    expect(session.content.rows).toEqual([
      ["Dead bug", "3", ""],
      ["weight_kg", "", "82,5 kg"],
    ]);
  });

  it("adds notes as a trailing Uwagi column", () => {
    const [session] = buildTrainingSessions([
      result({ id: "a", details: [{ label: "Serie", value: "3" }], notes: "lewa strona słabsza" }),
      result({ id: "b", details: [{ label: "Serie", value: "4" }, { label: "Ciężar", value: "20" }], created_at: "2026-10-11T11:00:00Z" }),
    ]);
    expect(session.content.columns).toEqual(["Serie", "Ciężar", "Uwagi"]);
    expect(session.content.rows).toEqual([
      ["3", "", "lewa strona słabsza"],
      ["4", "20", ""],
    ]);
  });

  it("keeps Goat entries (source_persona_id null) in the day's personas", () => {
    const [session] = buildTrainingSessions([result({ source_persona_id: null })]);
    expect(session.personaIds).toEqual([null]);
  });
});

describe("sessionPersonasForCategory", () => {
  const base = { active: true, custom_result_category: null, plan_columns: ["Ćwiczenie"] } as Partial<Persona>;
  it("returns active personas of the category that have plan columns", () => {
    const personas = [
      { ...base, id: "t", type: "motor_coach" },
      { ...base, id: "d", type: "dietitian" },
      { ...base, id: "x", type: "personal_trainer", active: false },
      { ...base, id: "y", type: "personal_trainer", plan_columns: [] },
    ] as Persona[];
    expect(sessionPersonasForCategory(personas, "strength").map((p) => p.id)).toEqual(["t"]);
  });
});
