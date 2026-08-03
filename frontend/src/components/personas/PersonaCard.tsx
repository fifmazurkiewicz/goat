import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { useCreateChatSession } from "@/hooks/useChatSessions";
import { useSharePersona, useUpdatePersona } from "@/hooks/usePersonas";
import { ApiError } from "@/lib/api-client";
import { DETAIL_LEVEL_LABELS, PERSONA_TYPE_LABELS, personaAvatarColor, personaInitials } from "@/lib/persona-labels";
import type { Persona } from "@/types/api";

interface PersonaCardProps {
  persona: Persona;
  onOpenConfig: (persona: Persona) => void;
  onEdit: (persona: Persona) => void;
}

export function PersonaCard({ persona, onOpenConfig, onEdit }: PersonaCardProps) {
  const navigate = useNavigate();
  const updatePersona = useUpdatePersona();
  const sharePersona = useSharePersona();
  const createSession = useCreateChatSession();

  async function handleToggleActive(active: boolean) {
    try {
      await updatePersona.mutateAsync({ id: persona.id, input: { active } });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nie udało się zmienić statusu persony.");
    }
  }

  async function handleShare() {
    try {
      await sharePersona.mutateAsync({ id: persona.id, isShared: true });
      toast.success("Persona udostępniona community");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nie udało się udostępnić persony.");
    }
  }

  async function handleChat() {
    try {
      const session = await createSession.mutateAsync({ persona_id: persona.id });
      navigate(`/chat/${session.id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nie udało się utworzyć rozmowy.");
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <CardHeader className="flex-row items-start justify-between gap-2 space-y-0 p-0">
        <div className="flex items-center gap-2">
          <Avatar className="h-9 w-9">
            <AvatarFallback className={`${personaAvatarColor(persona.id)} text-white`}>
              {personaInitials(persona.name)}
            </AvatarFallback>
          </Avatar>
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {PERSONA_TYPE_LABELS[persona.type]}
            </div>
            <div className="text-base font-semibold leading-tight">{persona.name}</div>
          </div>
        </div>
        <Badge variant={persona.detail_level === "detailed" ? "default" : "secondary"}>
          {DETAIL_LEVEL_LABELS[persona.detail_level]}
        </Badge>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3 p-0">
        <p className="line-clamp-2 text-sm text-muted-foreground">{persona.system_prompt}</p>
        <div className="text-xs text-muted-foreground">{persona.chat_model}</div>
        <div className="h-px bg-border" />
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={persona.active} onCheckedChange={handleToggleActive} disabled={updatePersona.isPending} />
            Aktywna
          </label>
          {persona.is_shared ? (
            <Badge variant="outline">Udostępniona</Badge>
          ) : (
            <Button type="button" variant="ghost" size="sm" className="px-0" onClick={handleShare}>
              Udostępnij
            </Button>
          )}
        </div>
        <Button type="button" variant="ghost" size="sm" className="justify-start px-0" onClick={() => onOpenConfig(persona)}>
          Zobacz konfigurację →
        </Button>
        <div className="mt-auto flex gap-2">
          <Button type="button" variant="outline" className="flex-1" onClick={() => onEdit(persona)}>
            Edytuj
          </Button>
          <Button type="button" variant="secondary" className="flex-1" onClick={handleChat} disabled={createSession.isPending}>
            Porozmawiaj
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
