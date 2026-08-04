import { describe, expect, it } from "vitest";

import { parseSseEvent, parseSseEvents } from "@/lib/sse";

describe("parseSseEvent", () => {
  it("parsuje event token z pojedynczą linią data", () => {
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

  it("parsuje tool_result", () => {
    const chunk =
      'event: tool_result\ndata: {"tool_name":"log_result","summary":"Zapisano sprint 10m: 1.8s","success":true}';
    expect(parseSseEvent(chunk)).toEqual({
      type: "tool_result",
      tool_name: "log_result",
      summary: "Zapisano sprint 10m: 1.8s",
      success: true,
    });
  });

  it("parsuje done bez danych", () => {
    const chunk = "event: done\ndata: {}";
    expect(parseSseEvent(chunk)).toEqual({ type: "done" });
  });

  it("scala wielolinijkowe pole data zgodnie ze specyfikacją SSE", () => {
    const chunk = 'event: token\ndata: {"text":"linia1\\nlinia2"}';
    expect(parseSseEvent(chunk)).toEqual({ type: "token", text: "linia1\nlinia2" });
  });

  it("ignoruje linie komentarza (heartbeat ping) i zwraca null", () => {
    expect(parseSseEvent(": ping")).toBeNull();
  });

  it("zwraca null dla pustego chunku", () => {
    expect(parseSseEvent("")).toBeNull();
    expect(parseSseEvent("\n")).toBeNull();
  });

  it("obsługuje malformed JSON jako komunikat błędu, nie rzuca wyjątku", () => {
    const chunk = "event: error\ndata: not-json{{{";
    const result = parseSseEvent(chunk);
    expect(result?.type).toBe("error");
    expect((result as { message?: string })?.message).toBe("not-json{{{");
  });

  it("wywnioskowuje typ z payloadu gdy brak linii event:", () => {
    const chunk = 'data: {"type":"tool_call_start","tool_name":"log_result"}';
    expect(parseSseEvent(chunk)).toEqual({ type: "tool_call_start", tool_name: "log_result" });
  });

  it("rozdziela dwa eventy sklejone w jednym chunku bez podwójnego \\n\\n", () => {
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
