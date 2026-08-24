import { describe, expect, it } from "vitest";

import { MOBILE_BREAKPOINT_QUERY } from "@/hooks/useMediaQuery";

describe("MOBILE_BREAKPOINT_QUERY", () => {
  it("also catches low-height screens (iPhone landscape), not just width <768", () => {
    expect(MOBILE_BREAKPOINT_QUERY).toMatch(/max-width:\s*767px/);
    expect(MOBILE_BREAKPOINT_QUERY).toMatch(/max-height:\s*500px/);
  });
});
