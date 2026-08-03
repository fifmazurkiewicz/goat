import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { filterPersonasBySlug } from "@/lib/persona-filter";
import { personaAvatarColor, personaInitials } from "@/lib/persona-labels";
import type { Persona } from "@/types/api";

interface PersonaSlashAutocompleteProps {
  personas: Persona[];
  query: string;
  activeIndex: number;
  onSelect: (persona: Persona) => void;
}

export function PersonaSlashAutocomplete({ personas, query, activeIndex, onSelect }: PersonaSlashAutocompleteProps) {
  const matches = filterPersonasBySlug(personas, query);

  if (matches.length === 0) {
    return <div className="px-3 py-2 text-sm text-muted-foreground">Brak pasujących person.</div>;
  }

  return (
    <ul role="listbox" aria-label="Wybierz personę" className="max-h-64 overflow-y-auto py-1">
      {matches.map((persona, index) => (
        <li key={persona.id}>
          <button
            type="button"
            role="option"
            aria-selected={index === activeIndex}
            className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent ${
              index === activeIndex ? "bg-accent" : ""
            }`}
            onMouseDown={(e) => {
              e.preventDefault();
              onSelect(persona);
            }}
          >
            <Avatar className="h-6 w-6">
              <AvatarFallback className={`${personaAvatarColor(persona.id)} text-[10px] text-white`}>
                {personaInitials(persona.name)}
              </AvatarFallback>
            </Avatar>
            <span className="font-medium">{persona.name}</span>
            <span className="text-xs text-muted-foreground">/{persona.slug}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
