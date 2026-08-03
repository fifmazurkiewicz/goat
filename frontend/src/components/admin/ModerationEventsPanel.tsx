import { format } from "date-fns";
import { pl } from "date-fns/locale";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useModerationEvents } from "@/hooks/useAdmin";

const VERDICT_VARIANT: Record<string, "default" | "destructive" | "secondary" | "outline"> = {
  clean: "secondary",
  injection_attempt: "destructive",
  redefine_role: "destructive",
  off_topic: "outline",
};

/** Przegląd `moderation_events` (docs/technical/database-schema.md) — brak dostępu dla zwykłego usera, tylko admin. */
export function ModerationEventsPanel() {
  const { data: events, isLoading } = useModerationEvents();

  if (isLoading) return <p className="text-sm text-muted-foreground">Ładowanie…</p>;

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky left-0 bg-background">Data</TableHead>
            <TableHead>Wyzwalacz</TableHead>
            <TableHead>Werdykt</TableHead>
            <TableHead>Fragment</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(events ?? []).map((event) => (
            <TableRow key={event.id}>
              <TableCell className="sticky left-0 bg-background text-muted-foreground">
                {format(new Date(event.created_at), "d MMM yyyy, HH:mm", { locale: pl })}
              </TableCell>
              <TableCell>{event.trigger_type}</TableCell>
              <TableCell>
                <Badge variant={VERDICT_VARIANT[event.classifier_verdict] ?? "outline"}>
                  {event.classifier_verdict}
                </Badge>
              </TableCell>
              <TableCell className="max-w-sm truncate text-muted-foreground" title={event.raw_snippet}>
                {event.raw_snippet}
              </TableCell>
            </TableRow>
          ))}
          {(events ?? []).length === 0 ? (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
                Brak zarejestrowanych zdarzeń moderacji.
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </div>
  );
}
