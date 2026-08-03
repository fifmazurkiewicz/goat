import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { usePersonaStore } from "@/store/usePersonaStore";
import type {
  Persona,
  PersonaCreateInput,
  PersonasListResponse,
  PersonaTemplate,
  PersonaUpdateInput,
  PlanTemplate,
} from "@/types/api";

const PERSONAS_KEY = ["personas"] as const;
const COMMUNITY_KEY = ["personas", "community"] as const;
const PERSONA_TEMPLATES_KEY = ["persona-templates"] as const;
const PLAN_TEMPLATES_KEY = ["plan-templates"] as const;

/**
 * Lista person usera — server state przez TanStack Query. `usePersonaStore` (zustand)
 * jest zsynchronizowany w `onSuccess` wyłącznie dla UI state współdzielonego z innymi
 * ekranami (aktywna persona w drawerze czatu itd.), docs/technical/frontend.md sekcja 2.
 */
export function usePersonas() {
  const setPersonas = usePersonaStore((state) => state.setPersonas);

  return useQuery({
    queryKey: PERSONAS_KEY,
    queryFn: async () => {
      const data = await apiFetch<PersonasListResponse>("/api/v1/personas");
      setPersonas(data.items);
      return data;
    },
  });
}

export function useCommunityPersonas() {
  return useQuery({
    queryKey: COMMUNITY_KEY,
    queryFn: () => apiFetch<Persona[]>("/api/v1/personas/community"),
  });
}

export function usePersonaTemplates() {
  return useQuery({
    queryKey: PERSONA_TEMPLATES_KEY,
    staleTime: Infinity,
    queryFn: () => apiFetch<PersonaTemplate[]>("/api/v1/persona-templates"),
  });
}

export function usePlanTemplates() {
  return useQuery({
    queryKey: PLAN_TEMPLATES_KEY,
    staleTime: Infinity,
    queryFn: () => apiFetch<PlanTemplate[]>("/api/v1/plan-templates"),
  });
}

export function useCreatePersona() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PersonaCreateInput) =>
      apiFetch<Persona>("/api/v1/personas", { method: "POST", body: input }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PERSONAS_KEY });
    },
  });
}

export function useUpdatePersona() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: PersonaUpdateInput }) =>
      apiFetch<Persona>(`/api/v1/personas/${id}`, { method: "PATCH", body: input }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PERSONAS_KEY });
    },
  });
}

export function useDeletePersona() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/api/v1/personas/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PERSONAS_KEY });
    },
  });
}

export function useSharePersona() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isShared }: { id: string; isShared: boolean }) =>
      apiFetch<Persona>(`/api/v1/personas/${id}/share`, {
        method: "PATCH",
        body: { is_shared: isShared },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PERSONAS_KEY });
      void queryClient.invalidateQueries({ queryKey: COMMUNITY_KEY });
    },
  });
}

export function useClonePersona() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Persona>(`/api/v1/personas/${id}/clone`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PERSONAS_KEY });
    },
  });
}
