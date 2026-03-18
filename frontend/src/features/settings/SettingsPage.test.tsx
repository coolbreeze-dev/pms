import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SettingsPage } from "./SettingsPage";
import { api } from "../../api/client";

vi.mock("../../api/client", () => ({
  api: {
    listAccounts: vi.fn(),
    getObservability: vi.fn(),
    getBrokerageSyncConfig: vi.fn(),
    getBrokerageSyncStatus: vi.fn(),
    previewImport: vi.fn(),
    commitImport: vi.fn(),
    createRefreshJob: vi.fn(),
    getJob: vi.fn(),
  },
}));

function renderSettings() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

describe("SettingsPage import workflow", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("renders reconciliation guidance after previewing an import", async () => {
    vi.mocked(api.listAccounts).mockResolvedValue([
      {
        id: 12,
        name: "Imported Brokerage",
        account_type: "Individual Brokerage",
        category: "brokerage",
        brokerage: "Fidelity",
        created_at: "2026-03-17T10:00:00",
      },
    ]);
    vi.mocked(api.getObservability).mockResolvedValue({
      environment: "development",
      auth_enabled: false,
      scheduler_running: true,
      database_ok: true,
      last_price_refresh: null,
      uptime_seconds: 120,
      total_requests: 10,
      total_errors: 0,
      error_rate_pct: "0",
      endpoints: [],
    });
    vi.mocked(api.getBrokerageSyncConfig).mockResolvedValue({
      provider: "disabled",
      consumer_key_configured: false,
      consumer_key_masked: null,
      snaptrade_client_id: null,
      snaptrade_redirect_uri: null,
    });
    vi.mocked(api.getBrokerageSyncStatus).mockResolvedValue({
      provider: "disabled",
      provider_label: "Brokerage Sync",
      enabled: false,
      configured: false,
      setup_instructions: null,
      user: null,
      synced_accounts: [],
      total_synced_holdings: 0,
      total_synced_transactions: 0,
    });
    vi.mocked(api.previewImport).mockResolvedValue({
      job_id: 99,
      adapter_name: "fidelity_positions",
      status: "previewed",
      row_count: 1,
      warnings: [],
      reconciliation: {
        suggested_account_id: 12,
        suggested_account_name: "Imported Brokerage",
        suggested_brokerage: "Fidelity",
        duplicate_rows_in_file: 0,
        rows_matching_existing_holdings: 1,
        rows_with_account_match: 1,
        rows_needing_review: 1,
        detected_brokerages: ["Fidelity"],
        account_suggestions: [
          {
            account_id: 12,
            account_name: "Imported Brokerage",
            brokerage: "Fidelity",
            matched_rows: 1,
            matched_existing_holdings: 1,
            reason: "Matched the source account name.",
          },
        ],
      },
      preview_rows: [
        {
          row_index: 1,
          ticker: "AAPL",
          name: "Apple",
          shares: "10",
          cost_basis: "1500",
          purchase_date: "2024-01-15",
          security_type: "equity",
          market: "us",
          currency: "USD",
          account_name: "Imported Brokerage",
          brokerage: "Fidelity",
          cost_basis_source: "reported",
          ticker_inferred: false,
          reconciliation_status: "review",
          matched_account_id: 12,
          matched_account_name: "Imported Brokerage",
          matched_account_brokerage: "Fidelity",
          matched_existing_holdings: 1,
          duplicate_row_count: 1,
          review_notes: ["1 existing holding already uses this ticker."],
        },
      ],
    });

    renderSettings();

    const uploadInput = await screen.findByLabelText("Upload spreadsheet");
    fireEvent.change(uploadInput, {
      target: {
        files: [new File(["ticker,shares,cost basis\nAAPL,10,1500"], "portfolio.csv", { type: "text/csv" })],
      },
    });
    fireEvent.click(screen.getByText("Preview import"));

    expect(await screen.findByText("Imported Brokerage · Fidelity")).toBeInTheDocument();
    expect(screen.getByText("Skip exact duplicate lots already present in the target account")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });
});
