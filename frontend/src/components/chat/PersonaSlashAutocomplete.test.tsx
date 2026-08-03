import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { PersonaSlashAutocomplete } from "@/components/chat/PersonaSlashAutocomplete";
import { filterPersonasBySlug } from "@/lib/persona-filter";
import type { Persona } from "@/types/api";

function makePersona(overrides: Partial<Persona>): Persona {
  return {
    id: overrides.id ?? "p1",
    user_id: "u1",
    type: "badminton_coach",
    name: "Kasia Wilk",
    system_prompt: "prompt",
    base_template_id: null,
    chat_model: "anthropic/claude-haiku-4.5",
    plan_template_id: null,
    template_overrides: null,
    detail_level: "simple",
    custom_result_category: null,
    slug: "trener_badmintona_kasia_wilk",
    is_shared: false,
    moderation_status: "approved",
    cloned_from_persona_id: null,
    active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("filterPersonasBySlug", () => {
  const personas = [
    makePersona({ id: "p1", name: "Kasia Wilk", slug: "trener_badmintona_kasia_wilk" }),
    makePersona({ id: "p2", name: "Marek Nowicki", slug: "dietetyk_marek_nowicki", type: "dietitian" }),
    makePersona({ id: "p3", name: "Nieaktywny", slug: "nieaktywny_ktos", active: false }),
  ];

  it("zwraca wszystkie aktywne persony dla pustego zapytania", () => {
    expect(filterPersonasBySlug(personas, "")).toHaveLength(2);
  });

  it("filtruje po prefiksie slugu", () => {
    const result = filterPersonasBySlug(personas, "diet");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Marek Nowicki");
  });

  it("filtruje po fragmencie nazwy", () => {
    const result = filterPersonasBySlug(personas, "kasia");
    expect(result).toHaveLength(1);
    expect(result[0].slug).toBe("trener_badmintona_kasia_wilk");
  });

  it("nigdy nie zwraca nieaktywnych person", () => {
    const result = filterPersonasBySlug(personas, "nieaktywny");
    expect(result).toHaveLength(0);
  });
});

describe("PersonaSlashAutocomplete", () => {
  const personas = [
    makePersona({ id: "p1", name: "Kasia Wilk", slug: "trener_badmintona_kasia_wilk" }),
    makePersona({ id: "p2", name: "Marek Nowicki", slug: "dietetyk_marek_nowicki", type: "dietitian" }),
  ];

  it("renderuje listę pasujących person i wywołuje onSelect po kliknięciu", () => {
    const onSelect = vi.fn();
    render(<PersonaSlashAutocomplete personas={personas} query="" activeIndex={0} onSelect={onSelect} />);

    expect(screen.getByText("Kasia Wilk")).toBeInTheDocument();
    expect(screen.getByText("Marek Nowicki")).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByText("Marek Nowicki"));
    expect(onSelect).toHaveBeenCalledWith(personas[1]);
  });

  it("pokazuje komunikat o braku dopasowań", () => {
    render(<PersonaSlashAutocomplete personas={personas} query="zzz" activeIndex={0} onSelect={vi.fn()} />);
    expect(screen.getByText("Brak pasujących person.")).toBeInTheDocument();
  });
});
