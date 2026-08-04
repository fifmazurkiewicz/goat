import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { AdminAuditLogEntry, AdminDeployInfo, AdminUser, ModerationEvent } from "@/types/api";

const ADMIN_USERS_KEY = ["admin", "users"] as const;

export function useAdminUsers() {
  return useQuery({
    queryKey: ADMIN_USERS_KEY,
    queryFn: () => apiFetch<AdminUser[]>("/api/v1/admin/users"),
  });
}

/** ADR-12 — limit aktywnych person PER KONTO, edytowalny przez admina. */
export function useUpdatePersonaLimit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, maxActivePersonas }: { userId: string; maxActivePersonas: number }) =>
      apiFetch<AdminUser>(`/api/v1/admin/users/${userId}/persona-limit`, {
        method: "PATCH",
        body: { max_active_personas: maxActivePersonas },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY });
    },
  });
}

/** ADR-16 — budżet USD per konto, edytowalny przez admina (BEZ etykiet Free/Pro). */
export function useUpdateUsageBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, usageBudgetUsd }: { userId: string; usageBudgetUsd: number }) =>
      apiFetch<AdminUser>(`/api/v1/admin/users/${userId}/usage-budget`, {
        method: "PATCH",
        body: { usage_budget_usd: usageBudgetUsd },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY });
    },
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: (userId: string) =>
      apiFetch<{ reset_link?: string }>(`/api/v1/admin/users/${userId}/reset-password`, { method: "POST" }),
  });
}

export function useModerationEvents() {
  return useQuery({
    queryKey: ["admin", "moderation-events"],
    queryFn: () => apiFetch<ModerationEvent[]>("/api/v1/admin/moderation-events"),
  });
}

export function useAdminAuditLog() {
  return useQuery({
    queryKey: ["admin", "audit-log"],
    queryFn: () => apiFetch<AdminAuditLogEntry[]>("/api/v1/admin/audit-log"),
  });
}

export function useAdminDeployInfo() {
  return useQuery({
    queryKey: ["admin", "deploy-info"],
    queryFn: () => apiFetch<AdminDeployInfo>("/api/v1/admin/deploy-info"),
    staleTime: 60_000,
  });
}
