import { API_BASE_URL, toApiError } from "@/lib/api-client";
import { reportApiNetworkError } from "@/store/useApiHealthStore";

const STORAGE_KEY = "goat_dev_auth";

export interface DevAuthState {
  accessToken: string;
  userId: string;
  email: string;
}

export const isDevLoginEnabled = import.meta.env.VITE_ENABLE_DEV_LOGIN === "true";

export function loadDevAuth(): DevAuthState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as DevAuthState;
    if (!parsed.accessToken || !parsed.userId || !parsed.email) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveDevAuth(state: DevAuthState): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function clearDevAuth(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export async function signInWithDevCredentials(
  email: string,
  password: string
): Promise<DevAuthState> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/v1/auth/dev-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch (err) {
    reportApiNetworkError(err);
    throw err;
  }

  if (!res.ok) {
    throw await toApiError(res);
  }

  const body = (await res.json()) as {
    access_token: string;
    user_id: string;
    email: string;
  };

  const state: DevAuthState = {
    accessToken: body.access_token,
    userId: body.user_id,
    email: body.email,
  };
  saveDevAuth(state);
  return state;
}
