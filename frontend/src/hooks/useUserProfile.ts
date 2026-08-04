import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { UserProfile, UserProfileUpdate } from "@/types/api";

const USER_PROFILE_KEY = ["user-profile"] as const;

/**
 * `user_profile` (biometria, ADR-11) — WSPÓLNY dla wszystkich person usera, odróżnij
 * od systemowego `personas.persona_constraints` (niewidoczne w API). Używany m.in. w dialogu "Zobacz pełną konfigurację"
 * na /personas (co widzi dana persona) i na /profile (formularz-fallback).
 */
export function useUserProfile() {
  return useQuery({
    queryKey: USER_PROFILE_KEY,
    queryFn: () => apiFetch<UserProfile | null>("/api/v1/profile"),
  });
}

export function useUpdateUserProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UserProfileUpdate) =>
      apiFetch<UserProfile>("/api/v1/profile", { method: "PATCH", body: input }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: USER_PROFILE_KEY });
    },
  });
}
