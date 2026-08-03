import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useResetPassword, useUpdatePersonaLimit, useUpdateUsageBudget } from "@/hooks/useAdmin";
import { ApiError } from "@/lib/api-client";
import type { AdminUser } from "@/types/api";

/**
 * Kwota w USD (`cost_usd_used`/`usage_budget_usd`) BEZ etykiet "Free"/"Pro" (ADR-16 —
 * to nie są plany subskrypcyjne, tylko budżet ochronny). Pierwsza kolumna `sticky
 * left-0` + poziomy scroll (docs/technical/frontend.md sekcja 11).
 */
export function AdminUsersTable({ users }: { users: AdminUser[] }) {
  const updatePersonaLimit = useUpdatePersonaLimit();
  const updateUsageBudget = useUpdateUsageBudget();
  const resetPassword = useResetPassword();
  const [drafts, setDrafts] = useState<Record<string, { maxPersonas: string; budget: string }>>({});

  function draftFor(user: AdminUser) {
    return drafts[user.id] ?? { maxPersonas: String(user.max_active_personas), budget: String(user.usage_budget_usd) };
  }

  function setDraft(user: AdminUser, patch: Partial<{ maxPersonas: string; budget: string }>) {
    setDrafts((prev) => ({ ...prev, [user.id]: { ...draftFor(user), ...patch } }));
  }

  async function saveMaxPersonas(user: AdminUser) {
    const value = Number(draftFor(user).maxPersonas);
    if (!Number.isFinite(value) || value < 0 || value > 50) {
      toast.error("Limit person musi być liczbą 0–50.");
      return;
    }
    try {
      await updatePersonaLimit.mutateAsync({ userId: user.id, maxActivePersonas: value });
      toast.success("Zapisano limit person");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nie udało się zapisać limitu.");
    }
  }

  async function saveBudget(user: AdminUser) {
    const value = Number(draftFor(user).budget);
    if (!Number.isFinite(value) || value < 0 || value > 1000) {
      toast.error("Budżet musi być liczbą 0–1000 USD.");
      return;
    }
    try {
      await updateUsageBudget.mutateAsync({ userId: user.id, usageBudgetUsd: value });
      toast.success("Zapisano budżet");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nie udało się zapisać budżetu.");
    }
  }

  async function handleResetPassword(user: AdminUser) {
    try {
      await resetPassword.mutateAsync(user.id);
      toast.success(`Wysłano link resetu hasła dla ${user.email}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nie udało się zresetować hasła.");
    }
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky left-0 bg-background">Użytkownik</TableHead>
            <TableHead>Budżet (USD)</TableHead>
            <TableHead>Persony (limit)</TableHead>
            <TableHead className="text-right">Akcje</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user) => {
            const draft = draftFor(user);
            const isNearBudget = user.usage_budget_usd > 0 && user.cost_usd_used / user.usage_budget_usd >= 0.9;
            return (
              <TableRow key={user.id}>
                <TableCell className="sticky left-0 bg-background">
                  <div className="font-medium">{user.nick ?? user.email}</div>
                  <div className="text-xs text-muted-foreground">{user.email}</div>
                  {user.is_admin ? <Badge variant="outline">Admin</Badge> : null}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground tabular-nums">
                      ${user.cost_usd_used.toFixed(2)} /
                    </span>
                    <Input
                      className="h-8 w-20"
                      type="number"
                      step="0.01"
                      value={draft.budget}
                      onChange={(e) => setDraft(user, { budget: e.target.value })}
                    />
                    <Button size="sm" variant="outline" onClick={() => saveBudget(user)}>
                      Zapisz
                    </Button>
                    {isNearBudget ? <Badge variant="outline">Blisko limitu</Badge> : null}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {user.active_personas_count} /
                    </span>
                    <Input
                      className="h-8 w-16"
                      type="number"
                      value={draft.maxPersonas}
                      onChange={(e) => setDraft(user, { maxPersonas: e.target.value })}
                    />
                    <Button size="sm" variant="outline" onClick={() => saveMaxPersonas(user)}>
                      Zapisz
                    </Button>
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  <Button size="sm" variant="ghost" onClick={() => handleResetPassword(user)}>
                    Reset hasła
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
          {users.length === 0 ? (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
                Brak użytkowników.
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </div>
  );
}
