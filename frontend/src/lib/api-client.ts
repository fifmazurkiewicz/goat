import { useAuthStore } from "@/store/useAuthStore";
import { reportApiNetworkError, watchSlowApiRequest } from "@/store/useApiHealthStore";
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
 * Parses the backend error response in `{error: {code, message}}` format
 * (see docs/technical/architecture.md section 6 — AppError hierarchy).
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

/** Readable message for toasts — works even when `instanceof ApiError` fails. */
export function getErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

function getAccessToken(): string | undefined {
  return useAuthStore.getState().getAccessToken();
}

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

/**
 * Simple `fetch` wrapper that appends `Authorization: Bearer <token>` and
 * the API base URL. For streaming SSE (`/chat/.../message`) we use a separate
 * `streamChatMessage` function (docs/technical/frontend.md section 3), not this
 * helper — it needs access to `res.body` as a stream.
 */
export async function apiFetch<TResponse = unknown>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<TResponse> {
  const token = getAccessToken();
  const { body, headers, ...rest } = options;
  const finishWatch = watchSlowApiRequest();

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    finishWatch(false);
    reportApiNetworkError(err);
    throw err;
  }

  if (!res.ok) {
    finishWatch(false);
    throw await toApiError(res);
  }

  finishWatch(true);

  if (res.status === 204) {
    return undefined as TResponse;
  }

  return (await res.json()) as TResponse;
}

export { API_BASE_URL };

/** Authenticated download helper for non-JSON API responses (privacy export). */
export async function apiDownload(path: string): Promise<{ blob: Blob; filename: string }> {
  const token = getAccessToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!res.ok) throw await toApiError(res);
  const disposition = res.headers.get("content-disposition") ?? "";
  const filename = /filename="?([^";]+)"?/i.exec(disposition)?.[1] ?? "goat-dane.json";
  return { blob: await res.blob(), filename };
}
