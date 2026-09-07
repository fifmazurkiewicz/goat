import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  useResetPassword,
  useUpdateApproval,
  useUpdatePersonaLimit,
  useUpdateUsageBudget,
} from "@/hooks/useAdmin";
import { ApiError } from "@/lib/api-client";
import { useAuthStore } from "@/store/useAuthStore";
import type { AdminUser } from "@/types/api";

/**
 * Amount in USD (`cost_usd_used`/`usage_budget_usd`) WITHOUT "Free"/"Pro" labels (ADR-16 —
 * these are not subscription plans, just a protective budget). First column `sticky
 * left-0` + horizontal scroll (docs/technical/frontend.md section 11).
 */
export function AdminUsersTable({ users }: { users: AdminUser[] }) {
  const currentUserId = useAuthStore((state) => state.user?.id);
  const updatePersonaLimit = useUpdatePersonaLimit();
  const updateUsageBudget = useUpdateUsageBudget();
  const updateApproval = useUpdateApproval();
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

  async function handleApproval(user: AdminUser, isApproved: boolean) {
    try {
      await updateApproval.mutateAsync({ userId: user.id, isApproved });
      toast.success(isApproved ? "Konto zaakceptowane" : "Cofnięto dostęp");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nie udało się zmienić statusu.");
    }
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky left-0 bg-background">Użytkownik</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Budżet (USD)</TableHead>
            <TableHead>Persony (limit)</TableHead>
            <TableHead className="text-right">Akcje</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user) => {
            const draft = draftFor(user);
            const isNearBudget = user.usage_budget_usd > 0 && user.cost_usd_used / user.usage_budget_usd >= 0.9;
            const isSelf = user.id === currentUserId;
            return (
              <TableRow key={user.id}>
                <TableCell className="sticky left-0 bg-background">
                  <div className="font-medium">{user.email || "—"}</div>
                  {user.nick ? <div className="text-xs text-muted-foreground">{user.nick}</div> : null}
                  {user.is_admin ? <Badge variant="outline">Admin</Badge> : null}
                </TableCell>
                <TableCell>
                  <Badge variant={user.is_approved ? "secondary" : "outline"}>
                    {user.is_approved ? "Aktywne" : "Oczekuje"}
                  </Badge>
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
                  <div className="flex flex-wrap items-center justify-end gap-1">
                    {user.is_approved ? (
                      isSelf ? null : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void handleApproval(user, false)}
                          disabled={updateApproval.isPending}
                        >
                          Cofnij dostęp
                        </Button>
                      )
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => void handleApproval(user, true)}
                        disabled={updateApproval.isPending}
                      >
                        Akceptuj
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => handleResetPassword(user)}>
                      Reset hasła
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
          {users.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-muted-foreground">
                Brak użytkowników.
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </div>
  );
}
