import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

import { MessageList } from "@/components/chat/MessageList";
import { TEAM_LEAD_DISPLAY_LABEL } from "@/lib/team-lead";
import type { ChatMessage } from "@/types/api";

const goatMessage: ChatMessage = {
  id: "goat-1",
  session_id: "s1",
  role: "assistant",
  content: "Plan uruchomiony.",
  tool_calls: null,
  persona_id: null,
  invoked_via: null,
  created_at: "2026-08-04T12:00:00Z",
};

describe("MessageList", () => {
  beforeEach(() => {
    HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it("historia: assistant bez persona_id dostaje etykietę Goata", () => {
    render(
      <MessageList
        messages={[goatMessage]}
        personaLabelFor={() => TEAM_LEAD_DISPLAY_LABEL}
        streaming={null}
      />
    );
    expect(screen.getByText(TEAM_LEAD_DISPLAY_LABEL)).toBeInTheDocument();
    expect(screen.getByText("Plan uruchomiony.")).toBeInTheDocument();
  });

  it("streaming: status bez tokenów → StreamingStatusLine", () => {
    render(
      <MessageList
        messages={[]}
        personaLabelFor={() => null}
        streaming={{
          content: "",
          personaId: null,
          personaLabel: TEAM_LEAD_DISPLAY_LABEL,
          statusLabel: "Goat · Kierownik Zespołu analizuje…",
          toolResults: [],
          consultDetails: [],
        }}
      />
    );
    expect(screen.getByText("Goat · Kierownik Zespołu analizuje…")).toBeInTheDocument();
  });

  it("po załadowaniu historii kotwiczy widok na dole (ostatnia wiadomość)", () => {
    const older: ChatMessage = { ...goatMessage, id: "older", content: "Stara wiadomość." };
    const latest: ChatMessage = { ...goatMessage, id: "latest", content: "Najnowsza wiadomość." };

    render(
      <MessageList messages={[older, latest]} personaLabelFor={() => TEAM_LEAD_DISPLAY_LABEL} streaming={null} />
    );

    expect(screen.getByText("Najnowsza wiadomość.")).toBeInTheDocument();
    expect(screen.getByTestId("chat-history-end")).toBeInTheDocument();
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("streaming: tokeny + personaLabel → bubble z nagłówkiem Goata", () => {
    render(
      <MessageList
        messages={[]}
        personaLabelFor={() => null}
        streaming={{
          content: "Generuję plan…",
          personaId: null,
          personaLabel: TEAM_LEAD_DISPLAY_LABEL,
          statusLabel: "",
          toolResults: [],
          consultDetails: [],
        }}
      />
    );
    expect(screen.getByText(TEAM_LEAD_DISPLAY_LABEL)).toBeInTheDocument();
    expect(screen.getByText("Generuję plan…")).toBeInTheDocument();
  });
});
