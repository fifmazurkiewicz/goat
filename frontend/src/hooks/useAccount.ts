import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { Account, AccountUpdateInput } from "@/types/api";

const ACCOUNT_KEY = ["account"] as const;

/**
 * `GET/PATCH /api/v1/account` (ADR-15) — celowo OSOBNY endpoint od `/api/v1/profile`
 * (biometria, ADR-11). Motyw NIE jest tu — czysto localStorage (`useThemeStore`).
 */
export function useAccount() {
  return useQuery({
    queryKey: ACCOUNT_KEY,
    queryFn: () => apiFetch<Account>("/api/v1/account"),
  });
}

export function useUpdateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AccountUpdateInput) =>
      apiFetch<Account>("/api/v1/account", { method: "PATCH", body: input }),
    onSuccess: (data) => {
      queryClient.setQueryData(ACCOUNT_KEY, data);
    },
  });
}
