import type { ChatSession } from "@/types/api";

/** Spójny fallback tytułu sesji w całym UI (lista, header, dialogi). */
export function sessionDisplayTitle(
  session: Pick<ChatSession, "title" | "session_type">,
  fallback = "Bez tytułu"
): string {
  const trimmed = session.title?.trim();
  if (trimmed) return trimmed;
  if (session.session_type === "general") return "Ogólna rozmowa";
  return fallback;
}

/** Tytuł w liście rozmów — krótszy fallback niż w headerze 1:1. */
export function sessionListTitle(session: Pick<ChatSession, "title" | "session_type">): string {
  const trimmed = session.title?.trim();
  if (trimmed) return trimmed;
  return session.session_type === "general" ? "Ogólna rozmowa" : "Rozmowa 1:1";
}

function updatedAtMs(session: Pick<ChatSession, "updated_at">): number {
  const ms = new Date(session.updated_at).getTime();
  return Number.isNaN(ms) ? 0 : ms;
}

/**
 * Najnowsza rozmowa wg `updated_at` — auto-wejście na mobile przy wejściu na `/chat`
 * bez `:sessionId` (spec 2026-08-17). `null` gdy user nie ma jeszcze rozmów.
 */
export function latestSessionId(sessions: ChatSession[] | undefined | null): string | null {
  if (!sessions || sessions.length === 0) return null;
  const newest = sessions.reduce((best, current) =>
    updatedAtMs(current) > updatedAtMs(best) ? current : best
  );
  return newest.id;
}
