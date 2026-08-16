import { describe, expect, it } from "vitest";

import {
  initialStreamStatus,
  personaThinkingStatus,
  personaToolStatus,
  resolveToolName,
  TEAM_STATUS_DEFAULT,
  PREPARING_STATUS,
  toolChipLabel,
} from "@/lib/chat-status";

describe("chat-status", () => {
  it("initialStreamStatus: general → Goat myśli, persona → preparing", () => {
    expect(initialStreamStatus("general")).toBe(TEAM_STATUS_DEFAULT);
    expect(TEAM_STATUS_DEFAULT).toMatch(/Goat/i);
    expect(TEAM_STATUS_DEFAULT.toLowerCase()).not.toContain("uzgadnia z zespołem");
    expect(initialStreamStatus("persona")).toBe(PREPARING_STATUS);
  });

  it("personaThinkingStatus z etykietą persony", () => {
    expect(personaThinkingStatus("Trener badmintona")).toBe("Trener badmintona analizuje…");
    expect(personaThinkingStatus(null)).toBe(PREPARING_STATUS);
  });

  it("personaToolStatus mapuje toole planu", () => {
    expect(personaToolStatus("Trener", "upsert_plan_items")).toBe("Trener zapisuje w Plany…");
    expect(personaToolStatus("Dietetyk", "rebuild_plan")).toBe("Dietetyk przebudowuje plan…");
  });

  it("personaToolStatus: nieznany tool + brak persony", () => {
    expect(personaToolStatus(null, "future_tool")).toBe("Wykonuje akcję…");
  });

  it("consult_persona: akcja i chip", () => {
    expect(personaToolStatus("Goat · Kierownik Zespołu", "consult_persona")).toBe(
      "Goat · Kierownik Zespołu konsultuje…"
    );
    expect(toolChipLabel("consult_persona")).toBe("Konsultacja");
  });

  it("resolveToolName: tool_name lub name z BE", () => {
    expect(resolveToolName({ tool_name: "log_result" })).toBe("log_result");
    expect(resolveToolName({ name: "update_user_profile" })).toBe("update_user_profile");
    expect(resolveToolName({})).toBeNull();
  });
});
