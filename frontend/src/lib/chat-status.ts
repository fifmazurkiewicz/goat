/**
 * Mapping of tools / stream phases to readable PL statuses (one line in MessageList).
 * Texts live on the FE — once we have 3+ new tools, this can move to the BE (`status` event).
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

/** tool_result chip label — in Polish, without the raw identifier. */
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

/** "{Persona} is analyzing…" — after `persona_turn_start`, before tokens/tools. */
export function personaThinkingStatus(personaLabel: string | null | undefined): string {
  const name = personaLabel?.trim();
  return name ? `${name} analizuje…` : PREPARING_STATUS;
}

/** "{Persona} is saving a result…" — after `tool_call_start`. */
export function personaToolStatus(
  personaLabel: string | null | undefined,
  toolName: string
): string {
  const action = toolActionLabel(toolName);
  const name = personaLabel?.trim();
  return name ? `${name} ${action}…` : `${action.charAt(0).toUpperCase()}${action.slice(1)}…`;
}

/** Initial status before the first SSE event. */
export function initialStreamStatus(sessionType: "general" | "persona" | string): string {
  return sessionType === "general" ? TEAM_STATUS_DEFAULT : PREPARING_STATUS;
}

/** Team lead — before the trainers' replies. */
export function teamStatusLabel(message: string | null | undefined): string {
  const text = message?.trim();
  return text || TEAM_STATUS_DEFAULT;
}

/** Normalizes `tool_call_start` — the BE emits `name`, the FE contract is `tool_name`. */
export function resolveToolName(event: { tool_name?: unknown; name?: unknown }): string | null {
  if (typeof event.tool_name === "string" && event.tool_name.trim()) return event.tool_name;
  if (typeof event.name === "string" && event.name.trim()) return event.name;
  return null;
}
