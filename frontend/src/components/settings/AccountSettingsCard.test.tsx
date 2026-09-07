import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountSettingsCard } from "@/components/settings/AccountSettingsCard";
import { signOut as signOutSupabase } from "@/lib/supabase";
import { useAuthStore } from "@/store/useAuthStore";

vi.mock("@/lib/supabase", () => ({
  signOut: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/hooks/useAccount", () => ({
  useAccount: () => ({
    data: { id: "acc-1", nick: "Ada", is_admin: false },
  }),
  useUpdateAccount: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

function renderCard(queryClient: QueryClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return render(<AccountSettingsCard />, { wrapper: Wrapper });
}

describe("AccountSettingsCard logout", () => {
  afterEach(() => {
    useAuthStore.getState().signOut();
    vi.clearAllMocks();
  });

  it("shows a Wyloguj button", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderCard(queryClient);
    expect(screen.getByRole("button", { name: "Wyloguj" })).toBeInTheDocument();
  });

  it("on click signs out of Supabase, clears the auth store, and drops the query cache", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["account"], { id: "acc-1", nick: "Ada", is_admin: false });
    useAuthStore.setState({
      user: { id: "u1", email: "ada@example.com" } as never,
      session: { access_token: "tok" } as never,
      isInitialized: true,
    });

    renderCard(queryClient);
    fireEvent.click(screen.getByRole("button", { name: "Wyloguj" }));

    await waitFor(() => {
      expect(signOutSupabase).toHaveBeenCalledTimes(1);
      expect(useAuthStore.getState().user).toBeNull();
      expect(useAuthStore.getState().session).toBeNull();
      expect(queryClient.getQueryData(["account"])).toBeUndefined();
    });
  });
});
