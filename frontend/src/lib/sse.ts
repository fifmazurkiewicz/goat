import { API_BASE_URL, toApiError } from "@/lib/api-client";
import { useAuthStore } from "@/store/useAuthStore";
import { reportApiNetworkError } from "@/store/useApiHealthStore";
import type { ChatStreamEvent, SendMessageBody } from "@/types/chat-stream";
import type { PlanGenerationProgressEvent } from "@/types/api";

/**
 * Parses one SSE frame (text between blank-line separators) into a domain event.
 * The input format is the standard SSE fields: `event: <name>` and (one or more) `data: <json>`
 * lines — `sse-starlette` (`architecture.md` section 3) serializes `EventSourceResponse` like this.
 * Comment lines (`:` at the start, e.g. a heartbeat ping every 15s) are ignored and we return `null`
 * — that's not a domain event, just connection keep-alive.
 *
 * When two events end up in one chunk (missing `\n\n` between them), `parseSseEvents` splits them
 * on `event:` — otherwise `data:` glues into unparsable JSON and the FE shows a raw dump.
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

/** Extract complete SSE frames while retaining a possibly fragmented final frame. */
export function extractSseFrames(buffer: string): { frames: string[]; remainder: string } {
  const parts = buffer.split(/\r?\n\r?\n/);
  return { frames: parts.slice(0, -1), remainder: parts.at(-1) ?? "" };
}

function parseSingleSseEvent(chunk: string): ChatStreamEvent | null {
  const lines = chunk.split(/\r?\n/).filter((line) => line.length > 0 && !line.startsWith(":"));
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

export async function* streamPlanJobEvents({
  jobId,
  signal,
}: {
  jobId: string;
  signal: AbortSignal;
}): AsyncGenerator<PlanGenerationProgressEvent> {
  const token = useAuthStore.getState().getAccessToken();
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/v1/plans/jobs/${jobId}/events`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      signal,
    });
  } catch (err) {
    reportApiNetworkError(err);
    throw err;
  }
  if (!res.ok || !res.body) throw await toApiError(res);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const { frames, remainder } = extractSseFrames(buffer);
    buffer = remainder;
    for (const frame of frames) {
      for (const event of parseSseEvents(frame)) {
        const eventType = (event as { type: string }).type;
        if (eventType === "plan_progress" || eventType === "done") {
          yield event as unknown as PlanGenerationProgressEvent;
        }
      }
    }
  }
}

/**
 * `fetch` + `ReadableStream`, NOT `EventSource` (it does not support POST with body or
 * the `Authorization` header) — docs/technical/frontend.md section 3.
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
    // sse-starlette uses CRLF on the wire by default. Accept both legal styles,
    // including delimiters split across network reads, so tokens are not buffered
    // until EOF (or until the server's whole-turn timeout).
    const extracted = extractSseFrames(buffer);
    buffer = extracted.remainder;
    const { frames } = extracted;
    for (const chunk of frames) {
      for (const event of parseSseEvents(chunk)) {
        yield event;
      }
    }
  }

  for (const event of parseSseEvents(buffer)) {
    yield event;
  }
}
