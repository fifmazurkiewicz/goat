import { describe, expect, it, vi } from "vitest";

import {
  registerChatTurnAbort,
  stopChatTurn,
  unregisterChatTurnAbort,
} from "@/lib/chat-turn-control";

vi.mock("@/lib/api-client", () => ({
  apiFetch: vi.fn().mockResolvedValue(undefined),
}));

describe("chat-turn-control", () => {
  it("aborts the local stream and calls the cancel API", async () => {
    const controller = new AbortController();
    registerChatTurnAbort("sess-1", controller);

    await stopChatTurn("sess-1");

    expect(controller.signal.aborted).toBe(true);
    unregisterChatTurnAbort("sess-1");
  });
});
