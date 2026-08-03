import type { Session, User } from "@supabase/supabase-js";
import { create } from "zustand";

interface AuthState {
  user: User | null;
  session: Session | null;
  isAdmin: boolean;
  /** false do pierwszego `getSession` — chroni przed bounce OAuth → /login. */
  isInitialized: boolean;
  setSession: (session: Session | null) => void;
  setInitialized: () => void;
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
  isInitialized: false,
  setSession: (session) =>
    set({
      session,
      user: session?.user ?? null,
    }),
  setInitialized: () => set({ isInitialized: true }),
  signOut: () => set({ user: null, session: null, isAdmin: false }),
}));
