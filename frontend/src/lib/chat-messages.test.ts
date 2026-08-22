import { describe, expect, it } from "vitest";

import { streamErrorMessage, visibleChatMessages } from "@/lib/chat-messages";
import type { ChatMessage } from "@/types/api";

function msg(partial: Partial<ChatMessage> & Pick<ChatMessage, "id" | "role">): ChatMessage {
  return {
    session_id: "s1",
    content: "",
    tool_calls: null,
    persona_id: null,
    invoked_via: null,
    created_at: new Date().toISOString(),
    ...partial,
  };
}

const CONSULT_CALLS = {
  calls: [
    {
      id: "call-1",
      type: "function",
      function: { name: "consult_persona", arguments: '{"slug":"motoryka","question":"q"}' },
    },
  ],
};

describe("visibleChatMessages", () => {
  it("ukrywa role=tool i puste assistant bez konsultacji", () => {
    const messages = [
      msg({ id: "1", role: "user", content: "cześć" }),
      msg({ id: "2", role: "assistant", content: null as unknown as string }),
      msg({ id: "3", role: "tool", content: '{"status":"ok"}' }),
      msg({ id: "4", role: "assistant", content: "ok" }),
    ];
    expect(visibleChatMessages(messages).map((m) => m.id)).toEqual(["1", "4"]);
  });

  it("deduplikuje po id", () => {
    const messages = [
      msg({ id: "1", role: "user", content: "a" }),
      msg({ id: "1", role: "user", content: "a" }),
    ];
    expect(visibleChatMessages(messages)).toHaveLength(1);
  });

  it("doczepia konsultację do wiadomości Goata (GWT-4 historia)", () => {
    const messages = [
      msg({ id: "1", role: "user", content: "co z techniką?" }),
      msg({
        id: "2",
        role: "assistant",
        content: "",
        tool_calls: CONSULT_CALLS,
      }),
      msg({
        id: "3",
        role: "tool",
        content: JSON.stringify({
          status: "ok",
          slug: "motoryka",
          persona_label: "Bartek · Trener motoryczny",
          question: "jak poprawić skok?",
          answer: "Plyometria 2x tydzień.",
        }),
        tool_calls: { tool_call_id: "call-1" },
      }),
      msg({ id: "4", role: "assistant", content: "Odpowiedź Goata." }),
    ];
    const visible = visibleChatMessages(messages);
    expect(visible.map((m) => m.id)).toEqual(["1", "2", "4"]);
    expect(visible[1].consultDetails).toEqual([
      {
        toolCallId: "call-1",
        personaLabel: "Bartek · Trener motoryczny",
        question: "jak poprawić skok?",
        answer: "Plyometria 2x tydzień.",
      },
    ]);
  });

  it("roundtable — dwie konsultacje w kolejności wywołań (GWT-2)", () => {
    const twoCalls = {
      calls: [
        CONSULT_CALLS.calls[0],
        {
          id: "call-2",
          type: "function",
          function: { name: "consult_persona", arguments: "{}" },
        },
      ],
    };
    const messages = [
      msg({ id: "1", role: "assistant", content: "", tool_calls: twoCalls }),
      msg({
        id: "t1",
        role: "tool",
        content: JSON.stringify({ status: "ok", persona_label: "A", answer: "pierwsza" }),
        tool_calls: { tool_call_id: "call-1" },
      }),
      msg({
        id: "t2",
        role: "tool",
        content: JSON.stringify({ status: "ok", persona_label: "B", question: "pyt?", answer: "druga" }),
        tool_calls: { tool_call_id: "call-2" },
      }),
    ];
    const visible = visibleChatMessages(messages);
    expect(visible).toHaveLength(1);
    expect(visible[0].consultDetails?.map((d) => d.answer)).toEqual(["pierwsza", "druga"]);
  });

  it("błąd konsultacji i złamany JSON nie tworzą załącznika (GWT-3)", () => {
    const messages = [
      msg({ id: "1", role: "assistant", content: "", tool_calls: CONSULT_CALLS }),
      msg({
        id: "t1",
        role: "tool",
        content: JSON.stringify({ error: "Brak aktywnej persony" }),
        tool_calls: { tool_call_id: "call-1" },
      }),
      msg({ id: "2", role: "assistant", content: "Goat sam odpowiada" }),
    ];
    const visible = visibleChatMessages(messages);
    expect(visible[0].consultDetails).toBeUndefined();
  });

  it("malformed JSON w role=tool nie wywala renderowania historii", () => {
    const messages = [
      msg({ id: "1", role: "assistant", content: "", tool_calls: CONSULT_CALLS }),
      msg({ id: "t1", role: "tool", content: "{{{nie-jest-json", tool_calls: { tool_call_id: "call-1" } }),
      msg({ id: "2", role: "assistant", content: "dalej działa" }),
    ];
    const visible = visibleChatMessages(messages);
    expect(visible.map((m) => m.id)).toEqual(["1", "2"]);
    expect(visible[0].consultDetails).toBeUndefined();
  });

  it("tool message z cudzego tool_call_id jest ignorowany (log_result itd.)", () => {
    const messages = [
      msg({ id: "1", role: "assistant", content: "", tool_calls: CONSULT_CALLS }),
      msg({
        id: "t1",
        role: "tool",
        content: JSON.stringify({ status: "ok", logged: true }),
        tool_calls: { tool_call_id: "inny-id" },
      }),
    ];
    const visible = visibleChatMessages(messages);
    expect(visible[0].consultDetails).toBeUndefined();
  });

  it("stary wpis bez question w response — fallback z arguments tool call", () => {
    const messages = [
      msg({ id: "1", role: "assistant", content: "", tool_calls: CONSULT_CALLS }),
      msg({
        id: "t1",
        role: "tool",
        content: JSON.stringify({
          status: "ok",
          slug: "motoryka",
          persona_label: "Bartek · Trener motoryczny",
          answer: "Plyometria.",
        }),
        tool_calls: { tool_call_id: "call-1" },
      }),
    ];
    const visible = visibleChatMessages(messages);
    expect(visible[0].consultDetails?.[0]?.question).toBe("q");
  });

  it("duplikat tool message (retry) nie dubluje konsultacji", () => {
    const toolMsg = () =>
      msg({
        id: "t1",
        role: "tool",
        content: JSON.stringify({ status: "ok", persona_label: "A", question: "q", answer: "a" }),
        tool_calls: { tool_call_id: "call-1" },
      });
    const visible = visibleChatMessages([
      msg({ id: "1", role: "assistant", content: "", tool_calls: CONSULT_CALLS }),
      toolMsg(),
      toolMsg(),
    ]);
    expect(visible[0].consultDetails).toHaveLength(1);
  });
});

describe("streamErrorMessage", () => {
  it("wyciąga message z JSON i dekoduje \\u escape", () => {
    expect(
      streamErrorMessage({
        message:
          '{"persona_id":"x","persona_label":"Dietetyk"} {"code":"internal_error","message":"Wyst\\u0105pi\\u0142 b\\u0142\\u0105d."}',
      })
    ).toBe("Wystąpił błąd.");
  });

  it("zwraca zwykły tekst bez zmian", () => {
    expect(streamErrorMessage({ message: "Limit budżetu." })).toBe("Limit budżetu.");
  });
});
