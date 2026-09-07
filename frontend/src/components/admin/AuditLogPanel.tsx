import { format } from "date-fns";
import { pl } from "date-fns/locale";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAdminAuditLog } from "@/hooks/useAdmin";
import type { AdminAuditAction } from "@/types/api";

const ACTION_LABELS: Record<AdminAuditAction, string> = {
  reset_password: "Reset hasła",
  edit_limits: "Edycja limitów",
  edit_persona_limit: "Edycja limitu person",
  edit_usage_budget: "Edycja budżetu",
  edit_approval: "Zmiana akceptacji",
};

/** Admin audit log (`admin_audit_log`) — who, what, to whom, when. */
export function AuditLogPanel() {
  const { data: entries, isLoading } = useAdminAuditLog();

  if (isLoading) return <p className="text-sm text-muted-foreground">Ładowanie…</p>;

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky left-0 bg-background">Data</TableHead>
            <TableHead>Akcja</TableHead>
            <TableHead>Użytkownik docelowy</TableHead>
            <TableHead>Szczegóły</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(entries ?? []).map((entry) => (
            <TableRow key={entry.id}>
              <TableCell className="sticky left-0 bg-background text-muted-foreground">
                {format(new Date(entry.created_at), "d MMM yyyy, HH:mm", { locale: pl })}
              </TableCell>
              <TableCell>{ACTION_LABELS[entry.action]}</TableCell>
              <TableCell className="text-muted-foreground">{entry.target_user_id}</TableCell>
              <TableCell className="max-w-sm truncate text-muted-foreground">
                {entry.details ? JSON.stringify(entry.details) : "—"}
              </TableCell>
            </TableRow>
          ))}
          {(entries ?? []).length === 0 ? (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
                Brak wpisów w logu audytowym.
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </div>
  );
}
