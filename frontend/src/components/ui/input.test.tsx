import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

describe("pola tekstowe — iOS zoom", () => {
  it("Input ma text-base na mobile (font ≥16px)", () => {
    render(<Input />);
    expect(document.querySelector("input")?.className).toMatch(/text-base/);
  });

  it("Textarea ma text-base na mobile (font ≥16px)", () => {
    render(<Textarea />);
    expect(document.querySelector("textarea")?.className).toMatch(/text-base/);
  });
});
