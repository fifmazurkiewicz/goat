import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConsultDetails } from "@/components/chat/ConsultDetails";
import type { ConsultDetail } from "@/types/api";

const detail: ConsultDetail = {
  toolCallId: "call-1",
  personaLabel: "Bartek · Trener motoryczny",
  question: "jak poprawić skok?",
  answer: "Plyometria 2x tydzień.",
};

describe("ConsultDetails", () => {
  it("nie renderuje się gdy brak konsultacji", () => {
    const { container } = render(<ConsultDetails details={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("domyślnie zwinięte — odpowiedź niewidoczna (GWT-1)", () => {
    render(<ConsultDetails details={[detail]} />);
    expect(screen.queryByText("Plyometria 2x tydzień.")).not.toBeInTheDocument();
    expect(screen.getByText(/Bartek · Trener motoryczny odpowiedział/)).toBeInTheDocument();
  });

  it("po kliknięciu pokazuje pytanie i odpowiedź (GWT-1)", () => {
    render(<ConsultDetails details={[detail]} />);
    fireEvent.click(screen.getByText(/Bartek · Trener motoryczny odpowiedział/));
    expect(screen.getByText("Plyometria 2x tydzień.")).toBeInTheDocument();
    expect(screen.getByText("jak poprawić skok?")).toBeInTheDocument();
  });

  it("wiele konsultacji — lista w kolejności (GWT-2)", () => {
    const second: ConsultDetail = {
      toolCallId: "call-2",
      personaLabel: "Ola · Dietetyczka",
      question: "dieta pod moc?",
      answer: "Białko 2g/kg.",
    };
    render(<ConsultDetails details={[detail, second]} />);
    expect(screen.getByText(/Bartek · Trener motoryczny odpowiedział/)).toBeInTheDocument();
    expect(screen.getByText(/Ola · Dietetyczka odpowiedział/)).toBeInTheDocument();
  });
});
