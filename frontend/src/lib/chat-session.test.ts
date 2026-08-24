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
  it("uses the title when it is set", () => {
    expect(sessionDisplayTitle({ title: "Poranny plan", session_type: "general" })).toBe("Poranny plan");
  });

  it("fallback for general sessions", () => {
    expect(sessionListTitle({ title: null, session_type: "general" })).toBe("Ogólna rozmowa");
    expect(sessionListTitle({ title: "  ", session_type: "persona" })).toBe("Rozmowa 1:1");
  });
});

describe("latestSessionId (auto-entry on mobile, spec 2026-08-17)", () => {
  it("returns the id of the conversation with the newest updated_at", () => {
    const sessions = [
      session("old", "2026-08-10T08:00:00Z"),
      session("newest", "2026-08-17T19:30:00Z"),
      session("middle", "2026-08-15T12:00:00Z"),
    ];

    expect(latestSessionId(sessions)).toBe("newest");
  });

  it("returns null when there are no conversations", () => {
    expect(latestSessionId([])).toBeNull();
    expect(latestSessionId(undefined)).toBeNull();
  });

  it("does not crash on an invalid date", () => {
    const sessions = [session("broken", "nie-data"), session("ok", "2026-08-17T19:30:00Z")];
    expect(latestSessionId(sessions)).toBe("ok");
  });
});
