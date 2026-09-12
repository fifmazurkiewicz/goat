import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { PrivacyConsent } from "@/types/api";

export const PRIVACY_CONSENT_KEY = ["privacy-consent"] as const;

export function usePrivacyConsent() {
  return useQuery({
    queryKey: PRIVACY_CONSENT_KEY,
    queryFn: () => apiFetch<PrivacyConsent>("/api/v1/privacy/consent"),
  });
}

export function useGrantPrivacyConsent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<PrivacyConsent>("/api/v1/privacy/consent/grant", { method: "POST", body: { accept_health_data: true, acknowledge_ai_disclosure: true } }),
    onSuccess: (consent) => queryClient.setQueryData(PRIVACY_CONSENT_KEY, consent),
  });
}

export function useWithdrawPrivacyConsent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<PrivacyConsent>("/api/v1/privacy/consent/withdraw", { method: "POST" }),
    onSuccess: (consent) => queryClient.setQueryData(PRIVACY_CONSENT_KEY, consent),
  });
}
