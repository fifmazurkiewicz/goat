import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { PlanItemTable } from "@/components/plans/PlanItemTable";
import type { PlanItemContent } from "@/types/api";

describe("PlanItemTable", () => {
  it("renderuje komunikat, gdy brak wierszy", () => {
    const content: PlanItemContent = { title: "Trening", columns: ["Ćwiczenie", "Serie"], rows: [], notes: null };
    render(<PlanItemTable content={content} variant="table" />);
    expect(screen.getByText("Brak pozycji do wyświetlenia.")).toBeInTheDocument();
  });

  it("renderuje wariant table z nagłówkami kolumn i wierszami", () => {
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

  it("renderuje wariant cards jako listę definicyjną etykieta/wartość", () => {
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

  it("obsługuje niedopasowaną długość wiersza względem kolumn (brakujące komórki jako —)", () => {
    const content: PlanItemContent = {
      title: "Trening",
      columns: ["Ćwiczenie", "Serie", "Powtórzenia"],
      rows: [["Przysiad", "4"]],
      notes: null,
    };
    render(<PlanItemTable content={content} variant="table" />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renderuje wiersze zapisane jako obiekty (format backendu)", () => {
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

  it("obsługuje wiersz dłuższy niż lista kolumn bez wyrzucania błędu (nadmiarowe komórki ignorowane)", () => {
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
