import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import { isDevLoginEnabled } from "@/lib/dev-auth";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!isDevLoginEnabled && (!supabaseUrl || !supabaseAnonKey)) {
  console.warn(
    "Brak VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY — skopiuj .env.example do .env.local i uzupełnij wartości."
  );
}

function createSupabaseClient(): SupabaseClient {
  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error("Supabase nie jest skonfigurowany.");
  }
  return createClient(supabaseUrl, supabaseAnonKey);
}

export const supabase = !isDevLoginEnabled ? createSupabaseClient() : (null as unknown as SupabaseClient);

/**
 * Logowanie przez Google OAuth (ADR-5) — tylko produkcja / bez VITE_ENABLE_DEV_LOGIN.
 */
export async function signInWithGoogle() {
  const client = createSupabaseClient();
  return client.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: `${window.location.origin}/personas`,
    },
  });
}

export async function signOut() {
  if (isDevLoginEnabled) return;
  const client = createSupabaseClient();
  return client.auth.signOut();
}
