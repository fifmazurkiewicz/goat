import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiStatusLamp } from "@/components/layout/ApiStatusLamp";

describe("ApiStatusLamp", () => {
  it("nie renderuje się gdy API działa (hidden)", () => {
    const { container } = render(<ApiStatusLamp lamp="hidden" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("po tapnięciu waking pokazuje tekst o budzeniu", () => {
    render(<ApiStatusLamp lamp="waking" />);
    fireEvent.click(screen.getByRole("button", { name: /budzimy aplikację/i }));
    expect(screen.getByText("Budzimy aplikację, poczekaj chwilę.")).toBeInTheDocument();
  });

  it("down: tap pokazuje tekst awarii i startuje ponowną próbę", () => {
    const onRetry = vi.fn();
    render(<ApiStatusLamp lamp="down" onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: /nie możemy połączyć/i }));
    expect(screen.getByText("Nie możemy połączyć się z serwerem. Spróbujemy ponownie.")).toBeInTheDocument();
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
