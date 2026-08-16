import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatHeader } from "@/components/chat/ChatHeader";
import type { ChatSession } from "@/types/api";

const generalSession: ChatSession = {
  id: "s1",
  user_id: "u1",
  persona_id: null,
  session_type: "general",
  title: "Poranny plan",
  created_at: "2026-08-16T10:00:00Z",
  updated_at: "2026-08-16T10:00:00Z",
};

describe("ChatHeader", () => {
  it("nie wciska instrukcji /slug w nagłówku — zostawia miejsce na historię", () => {
    render(<ChatHeader session={generalSession} persona={null} onOpenDrawer={() => undefined} />);

    expect(screen.getByText("Poranny plan")).toBeInTheDocument();
    expect(screen.queryByText(/trenerzy przez \/slug/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Goat koordynuje zespół/i)).not.toBeInTheDocument();
  });
});
