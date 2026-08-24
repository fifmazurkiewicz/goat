import type { ChatSession } from "@/types/api";

/** Consistent session title fallback across the UI (list, header, dialogs). */
export function sessionDisplayTitle(
  session: Pick<ChatSession, "title" | "session_type">,
  fallback = "Bez tytułu"
): string {
  const trimmed = session.title?.trim();
  if (trimmed) return trimmed;
  if (session.session_type === "general") return "Ogólna rozmowa";
  return fallback;
}

/** Title in the conversation list — shorter fallback than the 1:1 header. */
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
 * Newest conversation by `updated_at` — auto-entry on mobile when entering `/chat`
 * without `:sessionId` (spec 2026-08-17). `null` when the user has no conversations yet.
 */
export function latestSessionId(sessions: ChatSession[] | undefined | null): string | null {
  if (!sessions || sessions.length === 0) return null;
  const newest = sessions.reduce((best, current) =>
    updatedAtMs(current) > updatedAtMs(best) ? current : best
  );
  return newest.id;
}
