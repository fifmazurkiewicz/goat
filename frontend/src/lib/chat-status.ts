/**
 * Mapowanie tooli / faz streamu na czytelne statusy PL (jedna linia w MessageList).
 * Teksty żyją na FE — przy 3+ nowych toolach można przenieść na BE (event `status`).
 */

export const TOOL_ACTION_LABELS: Record<string, string> = {
  log_result: "zapisuje wynik",
  update_user_profile: "aktualizuje profil",
  get_plan: "przegląda plan",
  upsert_plan_items: "zapisuje w Plany",
  rebuild_plan: "uzgadnia plan między trenerami",
};

export const ROUTING_STATUS = "Dobieram trenera…";
export const PREPARING_STATUS = "Przygotowuję odpowiedź…";
export const DEFAULT_TOOL_ACTION = "wykonuje akcję";

export function toolActionLabel(toolName: string): string {
  return TOOL_ACTION_LABELS[toolName] ?? DEFAULT_TOOL_ACTION;
}

/** "{Persona} analizuje…" — po `persona_turn_start`, przed tokenami/toolami. */
export function personaThinkingStatus(personaLabel: string | null | undefined): string {
  const name = personaLabel?.trim();
  return name ? `${name} analizuje…` : PREPARING_STATUS;
}

/** "{Persona} zapisuje wynik…" — po `tool_call_start`. */
export function personaToolStatus(
  personaLabel: string | null | undefined,
  toolName: string
): string {
  const action = toolActionLabel(toolName);
  const name = personaLabel?.trim();
  return name ? `${name} ${action}…` : `${action.charAt(0).toUpperCase()}${action.slice(1)}…`;
}

/** Status startowy przed pierwszym eventem SSE. */
export function initialStreamStatus(sessionType: "general" | "persona" | string): string {
  return sessionType === "general" ? ROUTING_STATUS : PREPARING_STATUS;
}

/** Normalizacja `tool_call_start` — BE emituje `name`, kontrakt FE `tool_name`. */
export function resolveToolName(event: { tool_name?: unknown; name?: unknown }): string | null {
  if (typeof event.tool_name === "string" && event.tool_name.trim()) return event.tool_name;
  if (typeof event.name === "string" && event.name.trim()) return event.name;
  return null;
}
