import type { Session, User } from "@supabase/supabase-js";
import { create } from "zustand";

interface AuthState {
  user: User | null;
  session: Session | null;
  isAdmin: boolean;
  /** false do pierwszego `getSession` — chroni przed bounce OAuth → /login. */
  isInitialized: boolean;
  setSession: (session: Session | null) => void;
  setIsAdmin: (isAdmin: boolean) => void;
  setInitialized: () => void;
  signOut: () => void;
}

/**
 * Stan sesji Supabase. `isAdmin` pochodzi z `profiles.is_admin` via `GET /api/v1/account`
 * (docs/technical/database-schema.md) — nie z samego JWT.
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
      ...(session ? {} : { isAdmin: false }),
    }),
  setIsAdmin: (isAdmin) => set({ isAdmin }),
  setInitialized: () => set({ isInitialized: true }),
  signOut: () => set({ user: null, session: null, isAdmin: false }),
}));
