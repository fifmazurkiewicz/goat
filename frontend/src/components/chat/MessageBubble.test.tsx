import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MessageBubble } from "@/components/chat/MessageBubble";

describe("MessageBubble", () => {
  it("renderuje Markdown asystenta (pogrubienie, bez surowych **)", () => {
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

  it("wiadomość usera zostaje plain text", () => {
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
});
