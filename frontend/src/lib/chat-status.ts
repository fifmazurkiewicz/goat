/**
 * Mapowanie tooli / faz streamu na czytelne statusy PL (jedna linia w MessageList).
 * Teksty żyją na FE — przy 3+ nowych toolach można przenieść na BE (event `status`).
 */

export const TOOL_ACTION_LABELS: Record<string, string> = {
  log_result: "zapisuje wynik",
  update_user_profile: "aktualizuje profil",
  get_plan: "przegląda plan",
  upsert_plan_items: "zapisuje w Plany",
  rebuild_plan: "przebudowuje plan",
  consult_persona: "konsultuje",
};

export const ROUTING_STATUS = "Goat dobiera trenerów…";
export const TEAM_STATUS_DEFAULT = "Goat przygotowuje odpowiedź…";
export const PREPARING_STATUS = "Przygotowuję odpowiedź…";
export const DEFAULT_TOOL_ACTION = "wykonuje akcję";

export function toolActionLabel(toolName: string): string {
  return TOOL_ACTION_LABELS[toolName] ?? DEFAULT_TOOL_ACTION;
}

/** Etykieta chipa tool_result — po polsku, bez surowego identyfikatora. */
export function toolChipLabel(toolName: string): string {
  const labels: Record<string, string> = {
    log_result: "Wynik",
    update_user_profile: "Profil",
    get_plan: "Plan",
    upsert_plan_items: "Plany",
    rebuild_plan: "Przebudowa planu",
    consult_persona: "Konsultacja",
  };
  return labels[toolName] ?? "Akcja";
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
  return sessionType === "general" ? TEAM_STATUS_DEFAULT : PREPARING_STATUS;
}

/** Kierownik zespołu — przed odpowiedziami trenerów. */
export function teamStatusLabel(message: string | null | undefined): string {
  const text = message?.trim();
  return text || TEAM_STATUS_DEFAULT;
}

/** Normalizacja `tool_call_start` — BE emituje `name`, kontrakt FE `tool_name`. */
export function resolveToolName(event: { tool_name?: unknown; name?: unknown }): string | null {
  if (typeof event.tool_name === "string" && event.tool_name.trim()) return event.tool_name;
  if (typeof event.name === "string" && event.name.trim()) return event.name;
  return null;
}
