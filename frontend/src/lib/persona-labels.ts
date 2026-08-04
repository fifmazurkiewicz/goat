import type { DetailLevel, PersonaType } from "@/types/api";

export const PERSONA_TYPE_LABELS: Record<PersonaType, string> = {
  personal_trainer: "Trener personalny",
  dietitian: "Dietetyk",
  sport_psychologist: "Psycholog sportowy",
  psychologist: "Psycholog",
  motor_coach: "Trener motoryczny",
  badminton_coach: "Trener badmintona",
  custom: "Własna persona",
};

export const DETAIL_LEVEL_LABELS: Record<DetailLevel, string> = {
  simple: "Prosty",
  detailed: "Szczegółowy",
};

export const DETAIL_LEVEL_EXPLANATIONS: Record<DetailLevel, string> = {
  simple: "krótkie opisy, bez rozbudowanej techniki i uzasadnień.",
  detailed: "dodatkowa kolumna techniki/uzasadnienia w każdej rozpisce.",
};

/** Kolory awatarów person — silne kodowanie wizualne (nie tylko tekst), docs/technical/frontend.md sekcja 4. */
const AVATAR_PALETTE = [
  "bg-rose-500",
  "bg-amber-500",
  "bg-emerald-500",
  "bg-sky-500",
  "bg-violet-500",
  "bg-teal-500",
  "bg-orange-500",
];

export function personaAvatarColor(personaId: string): string {
  let hash = 0;
  for (let i = 0; i < personaId.length; i += 1) {
    hash = (hash * 31 + personaId.charCodeAt(i)) | 0;
  }
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}

export function formatPersonaDisplayLabel(name: string, type: PersonaType): string {
  const role = PERSONA_TYPE_LABELS[type];
  const trimmed = name.trim();
  if (trimmed.toLowerCase() === role.toLowerCase()) {
    return role;
  }
  return `${trimmed} · ${role}`;
}

export function personaInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}
