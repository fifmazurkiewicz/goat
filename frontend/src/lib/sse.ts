import { API_BASE_URL, toApiError } from "@/lib/api-client";
import { useAuthStore } from "@/store/useAuthStore";
import { reportApiNetworkError } from "@/store/useApiHealthStore";
import type { ChatStreamEvent, SendMessageBody } from "@/types/chat-stream";

/**
 * Parsuje jeden "chunk" SSE (tekst pomiędzy separatorami `\n\n`) na zdarzenie domenowe.
 * Format wejścia to standardowe pola SSE: `event: <nazwa>` i (jedna lub więcej) `data: <json>`
 * linii — `sse-starlette` (`architecture.md` sekcja 3) serializuje tak `EventSourceResponse`.
 * Linie komentarza (`:` na początku, np. heartbeat ping co 15s) są ignorowane i zwracamy `null`
 * — to nie jest zdarzenie domenowe, tylko utrzymanie połączenia.
 *
 * Gdy w jednym chunku wpadną dwa eventy (brak `\n\n` między nimi), `parseSseEvents` rozdziela
 * je po `event:` — inaczej `data:` skleja się w nieparsowalny JSON i FE pokazuje surowy dump.
 */
export function parseSseEvent(chunk: string): ChatStreamEvent | null {
  const events = parseSseEvents(chunk);
  return events[events.length - 1] ?? null;
}

export function parseSseEvents(chunk: string): ChatStreamEvent[] {
  const trimmed = chunk.trim();
  if (!trimmed) return [];

  const parts = trimmed.includes("\nevent:") ? trimmed.split(/\n(?=event:)/) : [trimmed];
  const events: ChatStreamEvent[] = [];
  for (const part of parts) {
    const event = parseSingleSseEvent(part);
    if (event) events.push(event);
  }
  return events;
}

function parseSingleSseEvent(chunk: string): ChatStreamEvent | null {
  const lines = chunk.split("\n").filter((line) => line.length > 0 && !line.startsWith(":"));
  if (lines.length === 0) return null;

  let eventName: string | undefined;
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  if (!eventName && dataLines.length === 0) return null;

  const rawData = dataLines.join("\n");
  let payload: Record<string, unknown> = {};
  if (rawData) {
    try {
      const parsed = JSON.parse(rawData) as unknown;
      if (parsed && typeof parsed === "object") {
        payload = parsed as Record<string, unknown>;
      }
    } catch {
      payload = { message: rawData };
    }
  }

  const type = eventName ?? (typeof payload.type === "string" ? payload.type : "error");

  return { ...payload, type } as ChatStreamEvent;
}

export interface StreamChatMessageOptions {
  sessionId: string;
  body: SendMessageBody;
  signal: AbortSignal;
}

/**
 * `fetch` + `ReadableStream`, NIE `EventSource` (nie wspiera POST z body ani nagłówka
 * `Authorization`) — docs/technical/frontend.md sekcja 3.
 */
export async function* streamChatMessage({
  sessionId,
  body,
  signal,
}: StreamChatMessageOptions): AsyncGenerator<ChatStreamEvent> {
  const token = useAuthStore.getState().getAccessToken();

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/v1/chat/sessions/${sessionId}/message`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    reportApiNetworkError(err);
    throw err;
  }

  if (!res.ok || !res.body) {
    throw await toApiError(res);
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      for (const event of parseSseEvents(chunk)) {
        yield event;
      }
    }
  }

  for (const event of parseSseEvents(buffer)) {
    yield event;
  }
}
