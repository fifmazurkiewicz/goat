import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PendingApprovalScreen } from "@/components/auth/PendingApprovalScreen";

describe("PendingApprovalScreen", () => {
  it("shows the waiting copy and actions", () => {
    const onCheckStatus = vi.fn();
    const onLogout = vi.fn();
    render(
      <PendingApprovalScreen
        onCheckStatus={onCheckStatus}
        onLogout={onLogout}
        isChecking={false}
      />
    );

    expect(screen.getByRole("heading", { name: "Konto oczekuje na akceptację" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sprawdź status" }));
    fireEvent.click(screen.getByRole("button", { name: "Wyloguj" }));
    expect(onCheckStatus).toHaveBeenCalledTimes(1);
    expect(onLogout).toHaveBeenCalledTimes(1);
  });
});
