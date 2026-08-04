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
