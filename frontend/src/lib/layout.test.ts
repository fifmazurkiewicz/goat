import { describe, expect, it } from "vitest";

import { isChatPath } from "@/lib/layout";

describe("isChatPath", () => {
  it("treats /chat and /chat/:id as the chat screen (no page scroll)", () => {
    expect(isChatPath("/chat")).toBe(true);
    expect(isChatPath("/chat/abc-123")).toBe(true);
  });

  it("does not match other routes", () => {
    expect(isChatPath("/chatty")).toBe(false);
    expect(isChatPath("/plans")).toBe(false);
    expect(isChatPath("/personas")).toBe(false);
  });
});
