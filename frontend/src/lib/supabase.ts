import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    "Brak VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY — skopiuj .env.example do .env.local i uzupełnij wartości."
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

/**
 * Logowanie wyłącznie przez Google OAuth (ADR-5) — bez magic linka.
 */
export async function signInWithGoogle() {
  // Po Google wracamy od razu do aplikacji (nie na gołe `/`), żeby uniknąć
  // wrażenia "strony głównej". URL musi być na liście Redirect URLs w Supabase.
  return supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: `${window.location.origin}/personas`,
    },
  });
}

export async function signOut() {
  return supabase.auth.signOut();
}
