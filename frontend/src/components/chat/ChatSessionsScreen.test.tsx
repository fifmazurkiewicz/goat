import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatSessionsScreen } from "@/components/chat/ChatSessionsScreen";
import type { ChatSession } from "@/types/api";

const sessions: ChatSession[] = [
  {
    id: "s1",
    user_id: "u1",
    persona_id: null,
    session_type: "general",
    title: "Poranny plan",
    created_at: "2026-08-16T10:00:00Z",
    updated_at: "2026-08-17T10:00:00Z",
  },
];

describe("ChatSessionsScreen (mobile /chat without session, GWT-2/GWT-3)", () => {
  it("shows the conversation history without forcing a new chat", () => {
    render(
      <ChatSessionsScreen
        sessions={sessions}
        personas={[]}
        activeSessionId={undefined}
        onSelectSession={() => undefined}
        onNewSession={() => undefined}
        onRenameSession={() => undefined}
        onDeleteSession={() => undefined}
      />
    );

    expect(screen.getByText("Poranny plan")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /nowa rozmowa/i })).toBeInTheDocument();
  });

  it("with no conversations shows a CTA instead of an empty screen", () => {
    render(
      <ChatSessionsScreen
        sessions={[]}
        personas={[]}
        activeSessionId={undefined}
        onSelectSession={() => undefined}
        onNewSession={() => undefined}
        onRenameSession={() => undefined}
        onDeleteSession={() => undefined}
      />
    );

    expect(screen.getByText(/brak rozmów/i)).toBeInTheDocument();
  });

  it("selecting a conversation from the list calls onSelectSession", () => {
    const onSelect = vi.fn();

    render(
      <ChatSessionsScreen
        sessions={sessions}
        personas={[]}
        activeSessionId={undefined}
        onSelectSession={onSelect}
        onNewSession={() => undefined}
        onRenameSession={() => undefined}
        onDeleteSession={() => undefined}
      />
    );

    fireEvent.click(screen.getByText("Poranny plan"));
    expect(onSelect).toHaveBeenCalledWith("s1");
  });
});
