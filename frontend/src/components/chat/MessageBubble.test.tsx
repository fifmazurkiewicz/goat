import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MessageBubble } from "@/components/chat/MessageBubble";

describe("MessageBubble", () => {
  it("renders assistant Markdown (bold, without raw **)", () => {
    render(
      <MessageBubble
        message={{
          role: "assistant",
          content: "**Waga bieżąca** i *kursywą*",
        }}
      />
    );
    expect(screen.getByText("Waga bieżąca").tagName).toBe("STRONG");
    expect(screen.getByText("kursywą").tagName).toBe("EM");
    expect(screen.queryByText(/\*\*/)).toBeNull();
  });

  it("keeps user messages as plain text", () => {
    render(
      <MessageBubble
        message={{
          role: "user",
          content: "**nie renderuj**",
        }}
      />
    );
    expect(screen.getByText("**nie renderuj**")).toBeInTheDocument();
  });

  it("renders Goat's header above the assistant reply", () => {
    render(
      <MessageBubble
        message={{ role: "assistant", content: "Plan w Plany." }}
        personaLabel="Goat · Kierownik Zespołu"
      />
    );
    expect(screen.getByText("Goat · Kierownik Zespołu")).toBeInTheDocument();
  });

  it("renders Markdown ## headings and lists", () => {
    render(
      <MessageBubble
        message={{
          role: "assistant",
          content: "## Co o Tobie wiem\n\n- waga 97 kg\n- cel: badminton",
        }}
      />
    );
    expect(screen.getByRole("heading", { level: 2, name: "Co o Tobie wiem" })).toBeInTheDocument();
    expect(screen.getByText("waga 97 kg")).toBeInTheDocument();
  });
});
