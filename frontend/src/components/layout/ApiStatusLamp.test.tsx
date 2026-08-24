import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiStatusLamp } from "@/components/layout/ApiStatusLamp";

describe("ApiStatusLamp", () => {
  it("does not render when the API is healthy (hidden)", () => {
    const { container } = render(<ApiStatusLamp lamp="hidden" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("on tapping the waking state shows the waking text", () => {
    render(<ApiStatusLamp lamp="waking" />);
    fireEvent.click(screen.getByRole("button", { name: /budzimy aplikację/i }));
    expect(screen.getByText("Budzimy aplikację, poczekaj chwilę.")).toBeInTheDocument();
  });

  it("down: tap shows the outage text and triggers a retry", () => {
    const onRetry = vi.fn();
    render(<ApiStatusLamp lamp="down" onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: /nie możemy połączyć/i }));
    expect(screen.getByText("Nie możemy połączyć się z serwerem. Spróbujemy ponownie.")).toBeInTheDocument();
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
