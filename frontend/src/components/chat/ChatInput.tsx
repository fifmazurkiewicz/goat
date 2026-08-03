import { useMemo, useRef, useState, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
import { PersonaSlashAutocomplete } from "@/components/chat/PersonaSlashAutocomplete";
import { filterPersonasBySlug } from "@/lib/persona-filter";
import type { Persona } from "@/types/api";

interface ChatInputProps {
  onSend: (content: string) => void;
  disabled: boolean;
  disabledReason?: string;
  /** Dropdown "/" tylko w sesji `general` — w sesji `persona` kontekst już wiadomy (ADR-13). */
  showSlashAutocomplete: boolean;
  activePersonas: Persona[];
  initialValue?: string;
}

/**
 * `ChatInput` (dumb) — disabled podczas streamu i przy 429; nasłuchuje na "/" na
 * starcie treści → `PersonaSlashAutocomplete` (docs/technical/frontend.md sekcja 4).
 */
export function ChatInput({
  onSend,
  disabled,
  disabledReason,
  showSlashAutocomplete,
  activePersonas,
  initialValue,
}: ChatInputProps) {
  const [value, setValue] = useState(initialValue ?? "");
  const [activeIndex, setActiveIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const slashQuery = useMemo(() => {
    if (!showSlashAutocomplete) return null;
    const match = /^\/([a-z0-9_]*)$/i.exec(value);
    return match ? match[1] : null;
  }, [value, showSlashAutocomplete]);

  const isAutocompleteOpen = slashQuery !== null && activePersonas.length > 0;
  const matches = isAutocompleteOpen ? filterPersonasBySlug(activePersonas, slashQuery ?? "") : [];

  function selectPersona(persona: Persona) {
    setValue(`/${persona.slug} `);
    setActiveIndex(0);
    textareaRef.current?.focus();
  }

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    setActiveIndex(0);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (isAutocompleteOpen && matches.length > 0) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((prev) => (prev + 1) % matches.length);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((prev) => (prev - 1 + matches.length) % matches.length);
        return;
      }
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        selectPersona(matches[activeIndex]);
        return;
      }
      if (event.key === "Escape") {
        setValue("");
        return;
      }
    }

    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="border-t p-4">
      <Popover open={isAutocompleteOpen}>
        <PopoverAnchor asChild>
          <div className="flex gap-2">
            <Textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setActiveIndex(0);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Napisz wiadomość..."
              rows={1}
              className="min-h-10 flex-1 resize-none"
              disabled={disabled}
            />
            <Button type="button" onClick={handleSubmit} disabled={disabled || !value.trim()}>
              Wyślij
            </Button>
          </div>
        </PopoverAnchor>
        <PopoverContent
          align="start"
          className="w-80 p-0"
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <PersonaSlashAutocomplete
            personas={activePersonas}
            query={slashQuery ?? ""}
            activeIndex={activeIndex}
            onSelect={selectPersona}
          />
        </PopoverContent>
      </Popover>
      {disabled && disabledReason ? <p className="mt-2 text-xs text-muted-foreground">{disabledReason}</p> : null}
      {!disabled && value.startsWith("/") && !isAutocompleteOpen ? (
        <p className="mt-2 text-xs text-muted-foreground/70">
          Wywołanie persony jako komendy — model rozpozna ją i odpowie w jej imieniu.
        </p>
      ) : null}
    </div>
  );
}
