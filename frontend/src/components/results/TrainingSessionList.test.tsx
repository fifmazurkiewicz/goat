import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { TrainingSessionList } from "@/components/results/TrainingSessionList";
import type { Persona, Result } from "@/types/api";

vi.mock("@/hooks/useExercises", () => ({ useExercises: () => ({ data: [] }) }));
vi.mock("@/hooks/useResults", () => ({
  useUpdateResult: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteResult: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

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

const personas = [{ id: "p1", name: "Bartek" }] as Persona[];

function renderList(results: Result[]) {
  return render(
    <MemoryRouter>
      <TrainingSessionList results={results} personas={personas} category="strength" />
    </MemoryRouter>
  );
}

describe("TrainingSessionList", () => {
  it("renders one card per day with exercise rows", () => {
    renderList([
      result({ id: "a", details: [{ label: "Ćwiczenie", value: "Dead bug" }, { label: "Serie", value: "3" }] }),
      result({ id: "b", logged_date: "2026-10-10", source_persona_id: null }),
    ]);
    expect(screen.getByRole("heading", { name: /11 października 2026/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /10 października 2026/i })).toBeInTheDocument();
    expect(screen.getAllByText("Dead bug").length).toBeGreaterThan(0);
    expect(screen.getByText(/Bartek/)).toBeInTheDocument();
    expect(screen.getByText(/Goat/)).toBeInTheDocument();
  });

  it("shows the empty state without results", () => {
    renderList([]);
    expect(
      screen.getByText("Brak zapisanych sesji — zgłoś trening w czacie albo dodaj go ręcznie.")
    ).toBeInTheDocument();
  });
});
