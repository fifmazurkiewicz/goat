import { describe, expect, it } from "vitest";

import {
  initialStreamStatus,
  personaThinkingStatus,
  personaToolStatus,
  resolveToolName,
  ROUTING_STATUS,
  PREPARING_STATUS,
} from "@/lib/chat-status";

describe("chat-status", () => {
  it("initialStreamStatus: general → routing, persona → preparing", () => {
    expect(initialStreamStatus("general")).toBe(ROUTING_STATUS);
    expect(initialStreamStatus("persona")).toBe(PREPARING_STATUS);
  });

  it("personaThinkingStatus z etykietą persony", () => {
    expect(personaThinkingStatus("Trener badmintona")).toBe("Trener badmintona analizuje…");
    expect(personaThinkingStatus(null)).toBe(PREPARING_STATUS);
  });

  it("personaToolStatus mapuje znane toole", () => {
    expect(personaToolStatus("Dietetyk", "update_user_profile")).toBe(
      "Dietetyk aktualizuje profil…"
    );
    expect(personaToolStatus("Trener", "log_result")).toBe("Trener zapisuje wynik…");
  });

  it("personaToolStatus: nieznany tool + brak persony", () => {
    expect(personaToolStatus(null, "future_tool")).toBe("Wykonuje akcję…");
  });

  it("resolveToolName: tool_name lub name z BE", () => {
    expect(resolveToolName({ tool_name: "log_result" })).toBe("log_result");
    expect(resolveToolName({ name: "update_user_profile" })).toBe("update_user_profile");
    expect(resolveToolName({})).toBeNull();
  });
});
