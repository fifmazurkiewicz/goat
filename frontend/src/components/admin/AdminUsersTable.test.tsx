import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminUsersTable } from "@/components/admin/AdminUsersTable";
import type { AdminUser } from "@/types/api";

vi.mock("@/hooks/useAdmin", () => ({
  useUpdatePersonaLimit: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateUsageBudget: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useResetPassword: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateApproval: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("@/store/useAuthStore", () => ({
  useAuthStore: (selector: (state: { user: { id: string } | null }) => unknown) =>
    selector({ user: { id: "admin-1" } }),
}));

function user(partial: Partial<AdminUser>): AdminUser {
  return {
    id: "u2",
    email: "user@example.com",
    nick: "Ada",
    is_admin: false,
    is_approved: false,
    max_active_personas: 5,
    active_personas_count: 0,
    cost_usd_used: 0,
    usage_budget_usd: 10,
    created_at: "2026-09-07T00:00:00Z",
    ...partial,
  };
}

describe("AdminUsersTable approval actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows Accept for a pending user and hides self-revoke", () => {
    render(
      <AdminUsersTable
        users={[
          user({ id: "admin-1", email: "fmazurkiewicz@gmail.com", nick: "Filip", is_admin: true, is_approved: true }),
          user({ id: "u2", is_approved: false }),
        ]}
      />
    );

    expect(screen.getByText("Oczekuje")).toBeInTheDocument();
    expect(screen.getByText("Aktywne")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Akceptuj" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cofnij dostęp" })).not.toBeInTheDocument();
  });

  it("shows revoke for another approved user", () => {
    render(
      <AdminUsersTable
        users={[user({ id: "u2", is_approved: true, email: "other@example.com" })]}
      />
    );

    expect(screen.getByRole("button", { name: "Cofnij dostęp" })).toBeInTheDocument();
  });
});
