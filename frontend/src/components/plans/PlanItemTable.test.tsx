import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { PlanItemTable } from "@/components/plans/PlanItemTable";
import type { PlanItemContent } from "@/types/api";

describe("PlanItemTable", () => {
  it("renders an empty-state message when there are no rows", () => {
    const content: PlanItemContent = { title: "Trening", columns: ["Ćwiczenie", "Serie"], rows: [], notes: null };
    render(<PlanItemTable content={content} variant="table" />);
    expect(screen.getByText("Brak pozycji do wyświetlenia.")).toBeInTheDocument();
  });

  it("renders the table variant with column headers and rows", () => {
    const content: PlanItemContent = {
      title: "Trening",
      columns: ["Ćwiczenie", "Serie", "Powtórzenia"],
      rows: [["Przysiad", "4", "8"]],
      notes: null,
    };
    render(<PlanItemTable content={content} variant="table" />);
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
    render(<PlanItemTable content={content} variant="cards" />);
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
    render(<PlanItemTable content={content} variant="table" />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders rows stored as objects (backend format)", () => {
    const content: PlanItemContent = {
      title: "Trening",
      columns: ["Ćwiczenie", "Serie", "Powtórzenia"],
      rows: [{ Ćwiczenie: "Przysiad", Serie: "4", Powtórzenia: "8" }],
      notes: null,
    };
    render(<PlanItemTable content={content} variant="table" />);
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
    expect(() => render(<PlanItemTable content={content} variant="table" />)).not.toThrow();
    expect(screen.getByText("Przysiad")).toBeInTheDocument();
  });
});
