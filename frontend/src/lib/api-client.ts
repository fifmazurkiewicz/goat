import { useAuthStore } from "@/store/useAuthStore";
import type { ApiErrorBody } from "@/types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

/**
 * Parsuje odpowiedź błędu backendu w formacie `{error: {code, message}}`
 * (patrz docs/technical/architecture.md sekcja 6 — hierarchia AppError).
 */
export async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body?.error?.code && body?.error?.message) {
      return new ApiError(body.error.code, body.error.message, response.status);
    }
  } catch {
    // fall through
  }
  return new ApiError("unknown_error", response.statusText || "Nieznany błąd", response.status);
}

/** Czytelny komunikat do toastów — działa też gdy `instanceof ApiError` zawodzi. */
export function getErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

function getAccessToken(): string | undefined {
  return useAuthStore.getState().session?.access_token;
}

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

/**
 * Prosty wrapper na `fetch` doklejający `Authorization: Bearer <token>` i
 * bazowy URL API. Do strumieniowania SSE (`/chat/.../message`) używamy
 * osobnej funkcji `streamChatMessage` (docs/technical/frontend.md sekcja 3),
 * nie tego helpera — potrzebuje dostępu do `res.body` jako stream.
 */
export async function apiFetch<TResponse = unknown>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<TResponse> {
  const token = getAccessToken();
  const { body, headers, ...rest } = options;

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    throw await toApiError(res);
  }

  if (res.status === 204) {
    return undefined as TResponse;
  }

  return (await res.json()) as TResponse;
}

export { API_BASE_URL };
