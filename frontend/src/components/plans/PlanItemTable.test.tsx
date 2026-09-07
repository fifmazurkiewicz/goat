import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { PlanItemTable } from "@/components/plans/PlanItemTable";
import type { Exercise, PlanItemContent } from "@/types/api";

vi.mock("@/hooks/useExercises", () => ({
  useExercises: () => ({
    data: [
      {
        id: "1",
        slug: "calf-raise",
        name: "Wspięcia na palce",
        name_en: "Calf Raise",
        persona_type: "motor_coach",
        level: "beginner",
        categories: ["Siłowe"],
        short_description: "opis",
        detail_full: "kroki",
        common_mistakes: null,
        photo_path: null,
      } satisfies Exercise,
    ],
  }),
}));

function renderTable(content: PlanItemContent, variant: "table" | "cards" = "table") {
  return render(
    <MemoryRouter>
      <PlanItemTable content={content} variant={variant} />
    </MemoryRouter>
  );
}

describe("PlanItemTable", () => {
  it("renders an empty-state message when there are no rows", () => {
    const content: PlanItemContent = { title: "Trening", columns: ["Ćwiczenie", "Serie"], rows: [], notes: null };
    renderTable(content);
    expect(screen.getByText("Brak pozycji do wyświetlenia.")).toBeInTheDocument();
  });

  it("renders the table variant with column headers and rows", () => {
    const content: PlanItemContent = {
      title: "Trening",
      columns: ["Ćwiczenie", "Serie", "Powtórzenia"],
      rows: [["Przysiad", "4", "8"]],
      notes: null,
    };
    renderTable(content);
    expect(screen.getByText("Ćwiczenie")).toBeInTheDocument();
    expect(screen.getByText("Przysiad")).toBeInTheDocument();
  });

  it("renders the cards variant as a definition list of label/value", () => {
    const content: PlanItemContent = {
      title: "Trening",
      columns: ["Ćwiczenie", "Serie"],
      rows: [["Przysiad", "4"]],
      notes: null,
    };
    renderTable(content, "cards");
    expect(screen.getByText("Ćwiczenie")).toBeInTheDocument();
    expect(screen.getByText("Przysiad")).toBeInTheDocument();
  });

  it("handles mismatched row length vs columns (missing cells rendered as —)", () => {
    const content: PlanItemContent = {
      title: "Trening",
      columns: ["Ćwiczenie", "Serie", "Powtórzenia"],
      rows: [["Przysiad", "4"]],
      notes: null,
    };
    renderTable(content);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders rows stored as objects (backend format)", () => {
    const content: PlanItemContent = {
      title: "Trening",
      columns: ["Ćwiczenie", "Serie", "Powtórzenia"],
      rows: [{ Ćwiczenie: "Przysiad", Serie: "4", Powtórzenia: "8" }],
      notes: null,
    };
    renderTable(content);
    expect(screen.getByText("Przysiad")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("handles rows longer than the column list without throwing (extra cells ignored)", () => {
    const content: PlanItemContent = {
      title: "Trening",
      columns: ["Ćwiczenie"],
      rows: [["Przysiad", "4", "8"]],
      notes: null,
    };
    expect(() => renderTable(content)).not.toThrow();
    expect(screen.getByText("Przysiad")).toBeInTheDocument();
  });

  it("links the Ćwiczenie column when Day is first (not column 0)", () => {
    const content: PlanItemContent = {
      title: "Trening",
      columns: ["Dzień (P/P/L)", "Ćwiczenie", "Serie"],
      rows: [["Czw (P)", "Calf raise 2-leg (pełny ROM, kontrola)", "3"]],
      notes: null,
    };
    renderTable(content);
    const link = screen.getByRole("link", {
      name: "Calf raise 2-leg (pełny ROM, kontrola)",
    });
    expect(link).toHaveAttribute("href", "/exercises/calf-raise");
    expect(screen.queryByRole("link", { name: "Czw (P)" })).not.toBeInTheDocument();
  });
});
