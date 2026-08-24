import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { UserProfile, UserProfileUpdate } from "@/types/api";

const USER_PROFILE_KEY = ["user-profile"] as const;

/**
 * `user_profile` (biometrics, ADR-11) — SHARED across all of the user's personas, distinct
 * from the system `personas.persona_constraints` (not exposed in the API). Used e.g. in the
 * "See full configuration" dialog on /personas (what a given persona sees) and on /profile
 * (form fallback).
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
