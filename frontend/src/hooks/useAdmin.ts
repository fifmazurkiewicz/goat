import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { AdminUser } from "@/types/api";

const ADMIN_USERS_KEY = ["admin", "users"] as const;

export function useAdminUsers() {
  return useQuery({
    queryKey: ADMIN_USERS_KEY,
    queryFn: () => apiFetch<AdminUser[]>("/api/v1/admin/users"),
  });
}

/** ADR-12 — active persona limit PER ACCOUNT, editable by admin. */
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

/** ADR-16 — USD budget per account, editable by admin (WITHOUT Free/Pro labels). */
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

export function useUpdateApproval() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, isApproved }: { userId: string; isApproved: boolean }) =>
      apiFetch<AdminUser>(`/api/v1/admin/users/${userId}/approval`, {
        method: "PATCH",
        body: { is_approved: isApproved },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY });
    },
  });
}
