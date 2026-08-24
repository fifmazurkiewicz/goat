import type { ChatMessage } from "@/types/api";

export const TEAM_LEAD_PERSONA_ID = "__team_lead__";
export const TEAM_LEAD_DISPLAY_LABEL = "Goat · Kierownik Zespołu";

/** Message from Goat (team lead) — assistant without persona_id in a general session. */
export function isTeamLeadAssistantMessage(
  message: ChatMessage,
  sessionType: "general" | "persona" | string
): boolean {
  if (sessionType !== "general" || message.role !== "assistant") return false;
  return message.persona_id == null || message.persona_id === TEAM_LEAD_PERSONA_ID;
}
