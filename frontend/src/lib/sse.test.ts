import { describe, expect, it } from "vitest";

import { extractSseFrames, parseSseEvent, parseSseEvents } from "@/lib/sse";

describe("parseSseEvent", () => {
  it("parses a token event with a single data line", () => {
    const chunk = 'event: token\ndata: {"text":"cześć"}';
    expect(parseSseEvent(chunk)).toEqual({ type: "token", text: "cześć" });
  });

  it("parsuje persona_turn_start (ADR-13)", () => {
    const chunk =
      'event: persona_turn_start\ndata: {"persona_id":"p1","persona_label":"Kasia Wilk · Trener badmintona"}';
    expect(parseSseEvent(chunk)).toEqual({
      type: "persona_turn_start",
      persona_id: "p1",
      persona_label: "Kasia Wilk · Trener badmintona",
    });
  });

  it("parses persona_turn_start with persona_id null (Goat, ADR-17)", () => {
    const chunk =
      'event: persona_turn_start\ndata: {"persona_id":null,"persona_label":"Goat · Kierownik Zespołu"}';
    expect(parseSseEvent(chunk)).toEqual({
      type: "persona_turn_start",
      persona_id: null,
      persona_label: "Goat · Kierownik Zespołu",
    });
  });

  it("parses team_status and team_phase", () => {
    expect(
      parseSseEvent('event: team_status\ndata: {"message":"Uzgodniam z dietetykiem…"}')
    ).toEqual({ type: "team_status", message: "Uzgodniam z dietetykiem…" });
    expect(
      parseSseEvent(
        'event: team_phase\ndata: {"phase":"planning","message":"Kierownik analizuje…"}'
      )
    ).toEqual({
      type: "team_phase",
      phase: "planning",
      message: "Kierownik analizuje…",
    });
  });

  it("parses tool_result", () => {
    const chunk =
      'event: tool_result\ndata: {"tool_name":"log_result","summary":"Zapisano sprint 10m: 1.8s","success":true}';
    expect(parseSseEvent(chunk)).toEqual({
      type: "tool_result",
      tool_name: "log_result",
      summary: "Zapisano sprint 10m: 1.8s",
      success: true,
    });
  });

  it("parses done without data", () => {
    const chunk = "event: done\ndata: {}";
    expect(parseSseEvent(chunk)).toEqual({ type: "done" });
  });

  it("joins multiline data fields per the SSE specification", () => {
    const chunk = 'event: token\ndata: {"text":"linia1\\nlinia2"}';
    expect(parseSseEvent(chunk)).toEqual({ type: "token", text: "linia1\nlinia2" });
  });

  it("parses CRLF frames emitted by sse-starlette", () => {
    const chunk = 'event: token\r\ndata: {"text":"od razu"}';
    expect(parseSseEvent(chunk)).toEqual({ type: "token", text: "od razu" });
  });

  it("extracts CRLF frames and retains a delimiter fragmented across reads", () => {
    const first = extractSseFrames('event: token\r\ndata: {"text":"a"}\r');
    expect(first.frames).toEqual([]);

    const second = extractSseFrames(`${first.remainder}\n\r\nevent: done\r\ndata: {}`);
    expect(second.frames).toEqual(['event: token\r\ndata: {"text":"a"}']);
    expect(second.remainder).toBe("event: done\r\ndata: {}");
  });

  it("ignores comment lines (heartbeat ping) and returns null", () => {
    expect(parseSseEvent(": ping")).toBeNull();
  });

  it("returns null for an empty chunk", () => {
    expect(parseSseEvent("")).toBeNull();
    expect(parseSseEvent("\n")).toBeNull();
  });

  it("treats malformed JSON as an error message, without throwing", () => {
    const chunk = "event: error\ndata: not-json{{{";
    const result = parseSseEvent(chunk);
    expect(result?.type).toBe("error");
    expect((result as { message?: string })?.message).toBe("not-json{{{");
  });

  it("infers the type from the payload when no event: line is present", () => {
    const chunk = 'data: {"type":"tool_call_start","tool_name":"log_result"}';
    expect(parseSseEvent(chunk)).toEqual({ type: "tool_call_start", tool_name: "log_result" });
  });

  it("splits two events glued together in one chunk without a double \\n\\n", () => {
    const chunk =
      'event: persona_turn_start\ndata: {"persona_id":"p1","persona_label":"Dietetyk"}\nevent: error\ndata: {"code":"internal_error","message":"Wystąpił nieoczekiwany błąd czatu."}';
    const events = parseSseEvents(chunk);
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({
      type: "persona_turn_start",
      persona_id: "p1",
      persona_label: "Dietetyk",
    });
    expect(events[1]).toEqual({
      type: "error",
      code: "internal_error",
      message: "Wystąpił nieoczekiwany błąd czatu.",
    });
  });
});
