import { describe, expect, it } from "vitest";

import {
  isTeamLeadAssistantMessage,
  TEAM_LEAD_DISPLAY_LABEL,
  TEAM_LEAD_PERSONA_ID,
} from "@/lib/team-lead";
import type { ChatMessage } from "@/types/api";

function assistant(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "1",
    session_id: "s1",
    role: "assistant",
    content: "Plan uruchomiony.",
    tool_calls: null,
    persona_id: null,
    invoked_via: null,
    created_at: "2026-08-04T12:00:00Z",
    ...overrides,
  };
}

describe("team-lead", () => {
  it("isTeamLeadAssistantMessage: general + assistant + null persona_id", () => {
    expect(isTeamLeadAssistantMessage(assistant(), "general")).toBe(true);
  });

  it("isTeamLeadAssistantMessage: legacy __team_lead__ id", () => {
    expect(
      isTeamLeadAssistantMessage(assistant({ persona_id: TEAM_LEAD_PERSONA_ID }), "general")
    ).toBe(true);
  });

  it("isTeamLeadAssistantMessage: trener ma persona_id", () => {
    expect(
      isTeamLeadAssistantMessage(assistant({ persona_id: "diet-uuid" }), "general")
    ).toBe(false);
  });

  it("isTeamLeadAssistantMessage: sesja persona nigdy nie jest Goat", () => {
    expect(isTeamLeadAssistantMessage(assistant(), "persona")).toBe(false);
  });

  it("isTeamLeadAssistantMessage: wiadomość usera", () => {
    expect(
      isTeamLeadAssistantMessage(assistant({ role: "user", content: "Hej" }), "general")
    ).toBe(false);
  });

  it("TEAM_LEAD_DISPLAY_LABEL", () => {
    expect(TEAM_LEAD_DISPLAY_LABEL).toBe("Goat · Kierownik Zespołu");
  });
});
