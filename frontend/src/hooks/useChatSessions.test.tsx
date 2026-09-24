import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { useCreateChatSession } from "@/hooks/useChatSessions";
import { apiFetch } from "@/lib/api-client";
import type { ChatSession } from "@/types/api";

vi.mock("@/lib/api-client", () => ({ apiFetch: vi.fn() }));

const existingSession: ChatSession = {
  id: "old", user_id: "user", persona_id: null, session_type: "general", title: null,
  created_at: "2026-09-24T10:00:00Z", updated_at: "2026-09-24T10:00:00Z",
};
const createdSession: ChatSession = {
  ...existingSession, id: "new", updated_at: "2026-09-24T10:01:00Z",
};

function CreateSessionButton() {
  const createSession = useCreateChatSession();
  return <button onClick={() => void createSession.mutateAsync({ persona_id: null })}>Create</button>;
}

describe("useCreateChatSession", () => {
  it("adds the returned session to the cache without waiting for a list refetch", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["chat-sessions"], [existingSession]);
    vi.mocked(apiFetch).mockResolvedValueOnce(createdSession);

    function Wrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    }

    render(<CreateSessionButton />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(queryClient.getQueryData<ChatSession[]>(["chat-sessions"])).toEqual([createdSession, existingSession]);
    });
  });
});
