import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import {
  CalendarViewSwitcher,
  resolveCalendarView,
} from "@/components/plans/CalendarViewSwitcher";

vi.mock("@/hooks/useMediaQuery", () => ({
  useIsMobile: () => true,
}));

vi.mock("@/components/plans/WeekAgendaView", () => ({
  WeekAgendaView: () => <div>week-view</div>,
}));

vi.mock("@/components/plans/MonthGridView", () => ({
  MonthGridView: () => <div>month-view</div>,
}));

const weekDays = [
  new Date("2026-09-07"),
  new Date("2026-09-08"),
  new Date("2026-09-09"),
  new Date("2026-09-10"),
  new Date("2026-09-11"),
  new Date("2026-09-12"),
  new Date("2026-09-13"),
];

describe("resolveCalendarView", () => {
  it("defaults to week on mobile until the user picks a view", () => {
    expect(resolveCalendarView(true, null)).toBe("week");
  });

  it("defaults to month on desktop until the user picks a view", () => {
    expect(resolveCalendarView(false, null)).toBe("month");
  });

  it("keeps a manual month choice on mobile", () => {
    expect(resolveCalendarView(true, "month")).toBe("month");
  });
});

describe("CalendarViewSwitcher", () => {
  it("shows the week/month switcher on mobile", () => {
    render(
      <MemoryRouter>
        <CalendarViewSwitcher
          view="week"
          onViewChange={vi.fn()}
          selectedDate={weekDays[0]}
          onSelectDate={vi.fn()}
          weekDays={weekDays}
          month={weekDays[0]}
          onMonthChange={vi.fn()}
          items={[]}
          personas={[]}
          onPrev={vi.fn()}
          onNext={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.getByRole("button", { name: "Tydzień" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Miesiąc" })).toBeInTheDocument();
  });

  it("lets the user switch to month on mobile", () => {
    const onViewChange = vi.fn();
    render(
      <MemoryRouter>
        <CalendarViewSwitcher
          view="week"
          onViewChange={onViewChange}
          selectedDate={weekDays[0]}
          onSelectDate={vi.fn()}
          weekDays={weekDays}
          month={weekDays[0]}
          onMonthChange={vi.fn()}
          items={[]}
          personas={[]}
          onPrev={vi.fn()}
          onNext={vi.fn()}
        />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Miesiąc" }));
    expect(onViewChange).toHaveBeenCalledWith("month");
  });
});
