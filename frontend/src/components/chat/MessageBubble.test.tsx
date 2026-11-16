import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MessageBubble } from "@/components/chat/MessageBubble";

const toastError = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({ toast: { error: toastError } }));

function mockClipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

describe("MessageBubble", () => {
  afterEach(() => {
    vi.useRealTimers();
    toastError.mockReset();
  });

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
    expect(screen.getByText("Wygenerowane przez AI")).toBeInTheDocument();
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
    expect(screen.queryByText("Wygenerowane przez AI")).not.toBeInTheDocument();
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

  it("copies a trainer reply as its raw Markdown and confirms it", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    mockClipboard(writeText);
    render(
      <MessageBubble
        message={{ role: "assistant", content: "**Rozgrzewka**\n- 10 min trucht" }}
        personaLabel="Trener · Motoryka"
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Kopiuj wiadomość" }));
    });

    expect(writeText).toHaveBeenCalledWith("**Rozgrzewka**\n- 10 min trucht");
    expect(screen.getByRole("button", { name: "Skopiowano wiadomość" })).toBeInTheDocument();
  });

  it("resets the copied confirmation after a moment", async () => {
    vi.useFakeTimers();
    mockClipboard(vi.fn().mockResolvedValue(undefined));
    render(<MessageBubble message={{ role: "assistant", content: "Plan gotowy." }} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Kopiuj wiadomość" }));
    });
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getByRole("button", { name: "Kopiuj wiadomość" })).toBeInTheDocument();
  });

  it("tells the user when the clipboard refuses the copy", async () => {
    mockClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(<MessageBubble message={{ role: "assistant", content: "Plan gotowy." }} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Kopiuj wiadomość" }));
    });

    expect(toastError).toHaveBeenCalledWith("Nie udało się skopiować wiadomości.");
    expect(screen.getByRole("button", { name: "Kopiuj wiadomość" })).toBeInTheDocument();
  });

  it("offers no copy action while the reply is still streaming", () => {
    render(<MessageBubble message={{ role: "assistant", content: "Piszę pla" }} streaming />);
    expect(screen.queryByRole("button", { name: /kopiuj/i })).not.toBeInTheDocument();
  });

  it("offers no copy action on the user's own messages", () => {
    render(<MessageBubble message={{ role: "user", content: "Cześć" }} />);
    expect(screen.queryByRole("button", { name: /kopiuj/i })).not.toBeInTheDocument();
  });
});
