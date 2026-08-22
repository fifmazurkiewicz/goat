import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PULL_THRESHOLD_PX, usePullToRefresh } from "@/hooks/usePullToRefresh";
import { useChatTurnStore } from "@/store/useChatTurnStore";

// jsdom nie ma PointerEvent — hook używa React.PointerEvent, więc syntetyzujemy
// zdarzenia przez Object.assign na Event (wystarcza dla handlerów pointer*).
function touchPointer(type: string, x: number, y: number): Event {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.assign(event, { pointerType: "touch", clientX: x, clientY: y, pointerId: 1 });
  return event;
}

interface HarnessProps {
  onRefresh?: () => Promise<void>;
  isLocked?: boolean;
}

function Harness({ onRefresh = async () => {}, isLocked = false }: HarnessProps) {
  const { pullDistance, isRefreshing, containerRef, handlers } = usePullToRefresh({
    onRefresh,
    isLocked,
    threshold: PULL_THRESHOLD_PX,
  });
  return (
    <div ref={containerRef} data-pull-to-refresh="" {...handlers} style={{ height: 400, overflow: "hidden" }}>
      <div data-testid="scroller" style={{ height: 100, overflowY: "auto" }}>
        <div style={{ height: 300 }}>treść</div>
      </div>
      <div data-testid="pull">{String(pullDistance)}</div>
      <div data-testid="refreshing">{String(isRefreshing)}</div>
    </div>
  );
}

describe("usePullToRefresh / PullToRefresh hook", () => {
  function drag(target: Element, from: number, to: number) {
    fireEvent(target, touchPointer("pointerdown", 100, from));
    fireEvent(target, touchPointer("pointermove", 100, Math.round((from + to) / 2)));
    fireEvent(target, touchPointer("pointermove", 100, to));
    fireEvent(target, touchPointer("pointerup", 100, to));
  }

  afterEach(() => {
    useChatTurnStore.setState({ isStreaming: false });
  });

  it("przekroczenie progu odpala refresh (GWT-1)", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(<Harness onRefresh={onRefresh} />);
    drag(screen.getByTestId("scroller").parentElement as Element, 50, 50 + PULL_THRESHOLD_PX + 20);
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId("refreshing").textContent).toBe("false"));
    expect(screen.getByTestId("pull").textContent).toBe("0");
  });

  it("poniżej progu — bez odświeżenia, dystans wraca do 0 (GWT-2)", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(<Harness onRefresh={onRefresh} />);
    drag(screen.getByTestId("scroller").parentElement as Element, 50, 40);
    await waitFor(() => expect(screen.getByTestId("pull").textContent).toBe("0"));
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("mysz (pointerType=mouse) nie triggeruje (GWT-4)", () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(<Harness onRefresh={onRefresh} />);
    const target = screen.getByTestId("scroller").parentElement as Element;
    fireEvent.pointerDown(target, { pointerType: "mouse", clientX: 100, clientY: 50 });
    fireEvent.pointerMove(target, { pointerType: "mouse", clientX: 100, clientY: 200 });
    fireEvent.pointerUp(target, { pointerType: "mouse", clientX: 100, clientY: 200 });
    expect(onRefresh).not.toHaveBeenCalled();
    expect(screen.getByTestId("pull").textContent).toBe("0");
  });

  it("poziomy swipe nie triggeruje (GWT-6)", () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(<Harness onRefresh={onRefresh} />);
    const target = screen.getByTestId("scroller").parentElement as Element;
    fireEvent(target, touchPointer("pointerdown", 100, 100));
    fireEvent(target, touchPointer("pointermove", 250, 130));
    fireEvent(target, touchPointer("pointerup", 300, 150));
    expect(onRefresh).not.toHaveBeenCalled();
    expect(screen.getByTestId("pull").textContent).toBe("0");
  });

  it("isLocked (stream w toku) blokuje gest (guard SSE)", () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(<Harness onRefresh={onRefresh} isLocked />);
    drag(screen.getByTestId("scroller").parentElement as Element, 50, 50 + PULL_THRESHOLD_PX + 40);
    expect(onRefresh).not.toHaveBeenCalled();
    expect(screen.getByTestId("pull").textContent).toBe("0");
  });

  it("w trakcie refreshu kolejny gest ignorowany (GWT-5)", async () => {
    let resolveRefresh: () => void = () => {};
    const onRefresh = vi.fn().mockImplementation(() => new Promise<void>((r) => (resolveRefresh = r)));
    render(<Harness onRefresh={onRefresh} />);
    const target = screen.getByTestId("scroller").parentElement as Element;
    drag(target, 50, 50 + PULL_THRESHOLD_PX + 20);
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));

    // Drugi pełny gest w trakcie oczekującego refreshu.
    drag(target, 50, 50 + PULL_THRESHOLD_PX + 40);
    expect(onRefresh).toHaveBeenCalledTimes(1);

    resolveRefresh();
    await waitFor(() => expect(screen.getByTestId("refreshing").textContent).toBe("false"));
  });
});
