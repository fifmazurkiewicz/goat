import { describe, expect, it } from "vitest";

import { latestSessionId, sessionDisplayTitle, sessionListTitle } from "@/lib/chat-session";
import type { ChatSession } from "@/types/api";

function session(id: string, updatedAt: string): ChatSession {
  return {
    id,
    user_id: "u1",
    persona_id: null,
    session_type: "general",
    title: null,
    created_at: "2026-08-01T10:00:00Z",
    updated_at: updatedAt,
  };
}

describe("sessionDisplayTitle / sessionListTitle", () => {
  it("używa tytułu, gdy jest ustawiony", () => {
    expect(sessionDisplayTitle({ title: "Poranny plan", session_type: "general" })).toBe("Poranny plan");
  });

  it("fallback dla sesji general", () => {
    expect(sessionListTitle({ title: null, session_type: "general" })).toBe("Ogólna rozmowa");
    expect(sessionListTitle({ title: "  ", session_type: "persona" })).toBe("Rozmowa 1:1");
  });
});

describe("latestSessionId (auto-wejście na mobile, spec 2026-08-17)", () => {
  it("zwraca id rozmowy z najnowszym updated_at", () => {
    const sessions = [
      session("old", "2026-08-10T08:00:00Z"),
      session("newest", "2026-08-17T19:30:00Z"),
      session("middle", "2026-08-15T12:00:00Z"),
    ];

    expect(latestSessionId(sessions)).toBe("newest");
  });

  it("zwraca null gdy nie ma rozmów", () => {
    expect(latestSessionId([])).toBeNull();
    expect(latestSessionId(undefined)).toBeNull();
  });

  it("nie wywraca się na niepoprawnej dacie", () => {
    const sessions = [session("broken", "nie-data"), session("ok", "2026-08-17T19:30:00Z")];
    expect(latestSessionId(sessions)).toBe("ok");
  });
});
