import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { MessageList } from "@/components/chat/MessageList";
import { TEAM_LEAD_DISPLAY_LABEL } from "@/lib/team-lead";
import type { ChatMessage } from "@/types/api";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: count }, (_, index) => ({
        index,
        key: index,
        start: index * 88,
      })),
    getTotalSize: () => count * 88,
    measureElement: vi.fn(),
    scrollToIndex: vi.fn(),
  }),
}));

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
        }}
      />
    );
    expect(screen.getByText("Goat · Kierownik Zespołu analizuje…")).toBeInTheDocument();
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
        }}
      />
    );
    expect(screen.getByText(TEAM_LEAD_DISPLAY_LABEL)).toBeInTheDocument();
    expect(screen.getByText("Generuję plan…")).toBeInTheDocument();
  });
});
