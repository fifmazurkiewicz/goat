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

describe("visibleChatMessages", () => {
  it("ukrywa role=tool i puste assistant", () => {
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
