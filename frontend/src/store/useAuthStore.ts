import type { Session, User } from "@supabase/supabase-js";
import { create } from "zustand";

import type { DevAuthState } from "@/lib/dev-auth";
import { clearDevAuth } from "@/lib/dev-auth";

interface AuthState {
  user: User | null;
  session: Session | null;
  devAuth: DevAuthState | null;
  isAdmin: boolean;
  /** false do pierwszego `getSession` — chroni przed bounce OAuth → /login. */
  isInitialized: boolean;
  setSession: (session: Session | null) => void;
  setDevAuth: (devAuth: DevAuthState | null) => void;
  setIsAdmin: (isAdmin: boolean) => void;
  setInitialized: () => void;
  signOut: () => void;
  isAuthenticated: () => boolean;
  getAccessToken: () => string | undefined;
}

/**
 * Stan sesji Supabase lub lokalnego dev auth. `isAdmin` pochodzi z `profiles.is_admin`
 * via `GET /api/v1/account` — nie z samego JWT.
 */
export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  session: null,
  devAuth: null,
  isAdmin: false,
  isInitialized: false,
  setSession: (session) =>
    set({
      session,
      user: session?.user ?? null,
      ...(session ? {} : { isAdmin: false }),
    }),
  setDevAuth: (devAuth) =>
    set({
      devAuth,
      user: devAuth
        ? ({
            id: devAuth.userId,
            email: devAuth.email,
          } as User)
        : null,
      ...(devAuth ? {} : { isAdmin: false }),
    }),
  setIsAdmin: (isAdmin) => set({ isAdmin }),
  setInitialized: () => set({ isInitialized: true }),
  signOut: () => {
    clearDevAuth();
    set({ user: null, session: null, devAuth: null, isAdmin: false });
  },
  isAuthenticated: () => Boolean(get().session || get().devAuth),
  getAccessToken: () => get().session?.access_token ?? get().devAuth?.accessToken,
}));
