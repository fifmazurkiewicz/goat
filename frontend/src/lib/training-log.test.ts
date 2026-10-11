import { describe, expect, it } from "vitest";

import { buildTrainingLog, logRangeStart, monthRanges } from "@/lib/training-log";
import type { Persona, PlanItem, Result } from "@/types/api";

function item(date: string, personaId = "trainer"): PlanItem {
  return {
    id: `${personaId}-${date}`,
    plan_id: "plan",
    item_date: date,
    item_type: "training",
    persona_id: personaId,
    content: { title: "Trening", columns: [], rows: [], notes: null },
    schema_version: 1,
    created_at: "2026-10-01T00:00:00Z",
  };
}

function result(date: string, overrides: Partial<Result> = {}): Result {
  return {
    id: `r-${date}-${overrides.metric ?? "m"}`,
    user_id: "u1",
    category: "strength",
    metric: "pompki",
    value: 20,
    unit: "powt.",
    logged_date: date,
    source: "manual",
    source_persona_id: null,
    is_custom: false,
    notes: null,
    details: null,
    created_at: "2026-10-01T00:00:00Z",
    ...overrides,
  };
}

const trainer = { id: "trainer", type: "personal_trainer", custom_result_category: null } as Persona;

// Wednesday
const today = new Date(2026, 9, 7);

describe("buildTrainingLog", () => {
  it("classifies days as done / missed / planned / empty and flags off-plan work", () => {
    const log = buildTrainingLog({
      start: new Date(2026, 9, 5),
      today,
      items: [item("2026-10-05"), item("2026-10-06"), item("2026-10-09")],
      results: [result("2026-10-05"), result("2026-10-07")],
    });
    expect(log.weeks).toHaveLength(1);
    const statuses = Object.fromEntries(log.weeks[0].days.map((day) => [day.date, day.status]));
    expect(statuses["2026-10-05"]).toBe("done");
    expect(statuses["2026-10-06"]).toBe("missed");
    expect(statuses["2026-10-07"]).toBe("done");
    expect(statuses["2026-10-08"]).toBe("empty");
    expect(statuses["2026-10-09"]).toBe("planned");
    expect(log.weeks[0].days.find((day) => day.date === "2026-10-07")?.offPlan).toBe(true);
    expect(log.weeks[0]).toMatchObject({ plannedDays: 3, doneDays: 2, donePlannedDays: 1 });
    expect(log.stats).toMatchObject({ daysSinceStart: 3, doneDays: 2, plannedPastDays: 2, donePlannedDays: 1 });
  });

  it("sums km and marks days before the start as out of range", () => {
    const log = buildTrainingLog({
      start: new Date(2026, 9, 6),
      today,
      items: [],
      results: [
        result("2026-10-06", { metric: "spacer", value: 5, unit: "km" }),
        result("2026-10-06", { metric: "bieg", value: 2.5, unit: " KM " }),
      ],
    });
    const [monday, tuesday] = log.weeks[0].days;
    expect(monday.inRange).toBe(false);
    expect(tuesday.km).toBe(7.5);
    expect(log.stats.km).toBe(7.5);
  });

  it("filters by persona: own plan items, own results and results in the persona's category", () => {
    const log = buildTrainingLog({
      start: new Date(2026, 9, 5),
      today,
      items: [item("2026-10-05", "dietitian"), item("2026-10-06")],
      results: [
        result("2026-10-05", { category: "diet" }),
        result("2026-10-06", { category: "custom", source_persona_id: "trainer" }),
        result("2026-10-07"),
      ],
      filter: { personaId: "trainer", persona: trainer },
    });
    const days = log.weeks[0].days;
    expect(days[0].status).toBe("empty");
    expect(days[1].status).toBe("done");
    expect(days[2].status).toBe("done");
  });
});

describe("logRangeStart / monthRanges", () => {
  it("starts at the earliest result, clamped to 12 months back", () => {
    expect(logRangeStart([], today)).toEqual(new Date(2026, 9, 1));
    expect(logRangeStart([result("2026-05-25")], today)).toEqual(new Date(2026, 4, 25));
    expect(logRangeStart([result("2020-01-01")], today)).toEqual(new Date(2025, 9, 1));
  });

  it("splits the range into whole months", () => {
    expect(monthRanges(new Date(2026, 8, 20), new Date(2026, 9, 11))).toEqual([
      { startDate: "2026-09-01", endDate: "2026-09-30" },
      { startDate: "2026-10-01", endDate: "2026-10-31" },
    ]);
  });
});
