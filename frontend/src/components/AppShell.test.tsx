import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    getAuthSession: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

function renderShell() {
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: <AppShell />,
        children: [{ index: true, element: <div>Dashboard content</div> }],
      },
    ],
    { initialEntries: ["/"] },
  );
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("AppShell", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("renders the auth gate when password auth is enabled", async () => {
    vi.mocked(api.getAuthSession).mockResolvedValue({
      enabled: true,
      authenticated: false,
      expires_at: null,
    });

    renderShell();

    expect(await screen.findByRole("button", { name: "Unlock" })).toBeInTheDocument();
    expect(screen.getByText("Protected session")).toBeInTheDocument();
  });

  it("renders the app shell when auth is disabled", async () => {
    vi.mocked(api.getAuthSession).mockResolvedValue({
      enabled: false,
      authenticated: true,
      expires_at: null,
    });

    renderShell();

    expect(await screen.findByText("Dashboard content")).toBeInTheDocument();
    expect(screen.getByText("Household Portfolio Tracker")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Readswell" })).not.toBeInTheDocument();
  });
});
