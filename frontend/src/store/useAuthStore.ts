import type { Session, User } from "@supabase/supabase-js";
import { create } from "zustand";

interface AuthState {
  user: User | null;
  session: Session | null;
  isAdmin: boolean;
  setSession: (session: Session | null) => void;
  signOut: () => void;
}

/**
 * Stan sesji Supabase. `isAdmin` pochodzi z `profiles.is_admin`
 * (docs/technical/database-schema.md) — ustawiane po fetchu profilu,
 * nie z samego JWT.
 */
export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  session: null,
  isAdmin: false,
  setSession: (session) =>
    set({
      session,
      user: session?.user ?? null,
    }),
  signOut: () => set({ user: null, session: null, isAdmin: false }),
}));
