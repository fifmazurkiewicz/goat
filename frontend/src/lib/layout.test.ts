import { describe, expect, it } from "vitest";

import { isChatPath } from "@/lib/layout";

describe("isChatPath", () => {
  it("traktuje /chat i /chat/:id jako ekran czatu (bez page-scroll)", () => {
    expect(isChatPath("/chat")).toBe(true);
    expect(isChatPath("/chat/abc-123")).toBe(true);
  });

  it("nie łapie innych tras", () => {
    expect(isChatPath("/chatty")).toBe(false);
    expect(isChatPath("/plans")).toBe(false);
    expect(isChatPath("/personas")).toBe(false);
  });
});
