import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { PrivacyConsentGate } from "@/components/privacy/PrivacyConsentGate";

vi.mock("@/hooks/usePrivacy", () => ({
  usePrivacyConsent: () => ({
    data: undefined,
    isPending: true,
    isError: false,
    refetch: vi.fn(),
  }),
  useGrantPrivacyConsent: () => ({
    isPending: false,
    isError: false,
    error: null,
    mutateAsync: vi.fn(),
  }),
}));

describe("PrivacyConsentGate", () => {
  it("does not block a non-sensitive route while consent is loading", () => {
    render(
      <MemoryRouter initialEntries={["/personas"]}>
        <PrivacyConsentGate>
          <div>Persony</div>
        </PrivacyConsentGate>
      </MemoryRouter>
    );

    expect(screen.getByText("Persony")).toBeInTheDocument();
    expect(screen.queryByText("Sprawdzanie zgód…")).not.toBeInTheDocument();
  });

  it("waits for consent on a sensitive route", () => {
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <PrivacyConsentGate>
          <div>Czat</div>
        </PrivacyConsentGate>
      </MemoryRouter>
    );

    expect(screen.getByText("Sprawdzanie zgód…")).toBeInTheDocument();
    expect(screen.queryByText("Czat")).not.toBeInTheDocument();
  });
});
