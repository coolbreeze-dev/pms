import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";

import { api } from "../../api/client";
import { knownBrokerages } from "../../lib/brokerages";
import { formatDate, formatNumber } from "../../lib/format";

interface ImportAccountForm {
  mode: "existing" | "new";
  account_id: string;
  name: string;
  account_type: string;
  category: string;
  brokerage: string;
  replace_existing: boolean;
  skip_existing_matching_holdings: boolean;
}

interface BrokerageSyncConfigForm {
  provider: string;
  snaptrade_client_id: string;
  snaptrade_consumer_key: string;
  snaptrade_redirect_uri: string;
}

const defaultImportAccount: ImportAccountForm = {
  mode: "existing",
  account_id: "",
  name: "",
  account_type: "Individual Brokerage",
  category: "brokerage",
  brokerage: "Vanguard",
  replace_existing: false,
  skip_existing_matching_holdings: true,
};

const defaultBrokerageSyncConfig: BrokerageSyncConfigForm = {
  provider: "disabled",
  snaptrade_client_id: "",
  snaptrade_consumer_key: "",
  snaptrade_redirect_uri: "http://127.0.0.1:5173/settings",
};

const brokerageSyncUiEnabled =
  ((import.meta.env.VITE_ENABLE_BROKERAGE_SYNC as string | undefined) ?? "false") === "true";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: api.listAccounts,
  });
  const observabilityQuery = useQuery({
    queryKey: ["observability"],
    queryFn: api.getObservability,
    refetchInterval: 15_000,
  });
  const brokerageSyncConfigQuery = useQuery({
    queryKey: ["brokerage-sync-config"],
    queryFn: api.getBrokerageSyncConfig,
    enabled: brokerageSyncUiEnabled,
  });
  const brokerageSyncQuery = useQuery({
    queryKey: ["brokerage-sync"],
    queryFn: api.getBrokerageSyncStatus,
    enabled: brokerageSyncUiEnabled,
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [refreshJobId, setRefreshJobId] = useState<string | null>(null);
  const [lastPortalUrl, setLastPortalUrl] = useState<string | null>(null);
  const [brokerageSyncNotice, setBrokerageSyncNotice] = useState<string | null>(null);
  const [isBrokerageConfigOpen, setIsBrokerageConfigOpen] = useState(false);
  const accountForm = useForm<ImportAccountForm>({ defaultValues: defaultImportAccount });
  const brokerageSyncConfigForm = useForm<BrokerageSyncConfigForm>({
    defaultValues: defaultBrokerageSyncConfig,
  });

  const previewMutation = useMutation({
    mutationFn: api.previewImport,
  });
  const invalidatePortfolioData = () => {
    queryClient.invalidateQueries({ queryKey: ["accounts"] });
    queryClient.invalidateQueries({ queryKey: ["holdings"] });
    queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    queryClient.invalidateQueries({ queryKey: ["analytics"] });
    queryClient.invalidateQueries({ queryKey: ["transactions"] });
    queryClient.invalidateQueries({ queryKey: ["investment-summary"] });
    queryClient.invalidateQueries({ queryKey: ["brokerage-sync"] });
    queryClient.invalidateQueries({ queryKey: ["brokerage-sync-config"] });
  };
  const commitMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => {
      if (!previewMutation.data) throw new Error("Preview an import first.");
      return api.commitImport(previewMutation.data.job_id, payload);
    },
    onSuccess: () => {
      invalidatePortfolioData();
      previewMutation.reset();
      setSelectedFile(null);
    },
  });
  const refreshMutation = useMutation({
    mutationFn: api.createRefreshJob,
    onSuccess: (job) => {
      setRefreshJobId(job.id);
      queryClient.invalidateQueries({ queryKey: ["job", job.id] });
    },
  });
  const jobQuery = useQuery({
    queryKey: ["job", refreshJobId],
    queryFn: () => api.getJob(refreshJobId!),
    enabled: Boolean(refreshJobId),
    refetchInterval: (query) =>
      query.state.data?.status === "pending" || query.state.data?.status === "running" ? 1_500 : false,
  });
  const connectMutation = useMutation({
    mutationFn: api.createBrokerageSyncPortal,
    onSuccess: (payload) => {
      setLastPortalUrl(payload.portal_url);
      if (typeof window !== "undefined") {
        window.open(payload.portal_url, "_blank", "noopener,noreferrer");
      }
      queryClient.invalidateQueries({ queryKey: ["brokerage-sync"] });
    },
  });
  const syncMutation = useMutation({
    mutationFn: api.runBrokerageSync,
    onSuccess: () => {
      invalidatePortfolioData();
    },
  });
  const saveBrokerageConfigMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.updateBrokerageSyncConfig(payload),
    onSuccess: (payload) => {
      invalidatePortfolioData();
      setBrokerageSyncNotice("Saved brokerage sync settings locally. You can connect the provider now.");
      brokerageSyncConfigForm.reset({
        provider: payload.provider,
        snaptrade_client_id: payload.snaptrade_client_id ?? "",
        snaptrade_consumer_key: "",
        snaptrade_redirect_uri: payload.snaptrade_redirect_uri ?? defaultBrokerageSyncConfig.snaptrade_redirect_uri,
      });
      setIsBrokerageConfigOpen(false);
    },
  });

  useEffect(() => {
    if (!brokerageSyncUiEnabled) return;
    if (!brokerageSyncConfigQuery.data) return;
    brokerageSyncConfigForm.reset({
      provider: brokerageSyncConfigQuery.data.provider,
      snaptrade_client_id: brokerageSyncConfigQuery.data.snaptrade_client_id ?? "",
      snaptrade_consumer_key: "",
      snaptrade_redirect_uri:
        brokerageSyncConfigQuery.data.snaptrade_redirect_uri ?? defaultBrokerageSyncConfig.snaptrade_redirect_uri,
    });
    if (!brokerageSyncConfigQuery.data.consumer_key_configured || brokerageSyncConfigQuery.data.provider === "disabled") {
      setIsBrokerageConfigOpen(true);
    }
  }, [brokerageSyncConfigForm, brokerageSyncConfigQuery.data]);

  useEffect(() => {
    if (!previewMutation.data) return;
    const suggestedAccountId = previewMutation.data.reconciliation.suggested_account_id;
    const firstRow = previewMutation.data.preview_rows[0];
    if (suggestedAccountId) {
      accountForm.setValue("mode", "existing");
      accountForm.setValue("account_id", String(suggestedAccountId));
      return;
    }
    if (firstRow?.account_name || firstRow?.brokerage) {
      accountForm.setValue("mode", "new");
      if (firstRow.account_name) {
        accountForm.setValue("name", firstRow.account_name);
      }
      if (firstRow.brokerage) {
        accountForm.setValue("brokerage", firstRow.brokerage);
      }
    }
  }, [accountForm, previewMutation.data]);

  function previewFile() {
    if (!selectedFile) return;
    previewMutation.mutate(selectedFile);
  }

  function commitImport() {
    const values = accountForm.getValues();
    const payload = {
      replace_existing: values.replace_existing,
      skip_existing_matching_holdings: values.replace_existing ? false : values.skip_existing_matching_holdings,
    };
    if (values.mode === "existing" && values.account_id) {
      commitMutation.mutate({ ...payload, account_id: Number(values.account_id) });
      return;
    }
    commitMutation.mutate({
      ...payload,
      account: {
        name: values.name,
        account_type: values.account_type,
        category: values.category,
        brokerage: values.brokerage,
      },
    });
  }

  function handleConnectBrokerage() {
    const syncState = brokerageSyncQuery.data;
    if (!syncState) return;
    if (!syncState.configured) {
      setBrokerageSyncNotice(
        syncState.setup_instructions ?? "Configure a brokerage sync provider before connecting accounts.",
      );
      return;
    }
    setBrokerageSyncNotice(null);
    connectMutation.mutate();
  }

  function handleRunBrokerageSync() {
    const syncState = brokerageSyncQuery.data;
    if (!syncState) return;
    if (!syncState.configured) {
      setBrokerageSyncNotice(
        syncState.setup_instructions ?? "Configure a brokerage sync provider before syncing accounts.",
      );
      return;
    }
    if (!syncState.user) {
      setBrokerageSyncNotice("Open the connection portal first, then run sync after authorization completes.");
      return;
    }
    setBrokerageSyncNotice(null);
    syncMutation.mutate();
  }

  function saveBrokerageSyncConfig(values: BrokerageSyncConfigForm) {
    setBrokerageSyncNotice(null);
    saveBrokerageConfigMutation.mutate({
      provider: values.provider,
      snaptrade_client_id: values.snaptrade_client_id || null,
      snaptrade_consumer_key: values.snaptrade_consumer_key || null,
      snaptrade_redirect_uri: values.snaptrade_redirect_uri || null,
    });
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Price cache</p>
            <h2>Refresh quotes and benchmark history</h2>
          </div>
          <button className="button button--primary" onClick={() => refreshMutation.mutate()}>
            Refresh prices
          </button>
        </div>
        {jobQuery.data ? (
          <p className="status-line">
            Job <strong>{jobQuery.data.status}</strong>
            {jobQuery.data.completed_at ? ` · completed ${formatDate(jobQuery.data.completed_at)}` : ""}
          </p>
        ) : (
          <p className="empty-state">No refresh job has been started in this session.</p>
        )}
      </section>

      {brokerageSyncUiEnabled ? (
        <section className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Brokerage sync</p>
              <h2>Connect accounts through a live brokerage API</h2>
            </div>
            <div className="form-actions">
              <button
                className="button button--ghost"
                onClick={handleConnectBrokerage}
                disabled={brokerageSyncQuery.isLoading || connectMutation.isPending}
              >
                {connectMutation.isPending
                  ? "Opening portal..."
                  : brokerageSyncQuery.data?.configured
                    ? "Connect brokerage"
                    : "Setup brokerage sync"}
              </button>
              <button
                className="button button--primary"
                onClick={handleRunBrokerageSync}
                disabled={brokerageSyncQuery.isLoading || syncMutation.isPending}
              >
                {syncMutation.isPending ? "Syncing..." : "Sync now"}
              </button>
            </div>
          </div>
          <div className="config-disclosure">
            <button
              className="button button--ghost"
              type="button"
              onClick={() => setIsBrokerageConfigOpen((current) => !current)}
            >
              {isBrokerageConfigOpen ? "Hide local brokerage credentials" : "Configure local brokerage credentials"}
            </button>
            {isBrokerageConfigOpen ? (
              <form
                className="form-grid panel__subsection"
                onSubmit={brokerageSyncConfigForm.handleSubmit(saveBrokerageSyncConfig)}
              >
                <label>
                  Provider
                  <select {...brokerageSyncConfigForm.register("provider")}>
                    <option value="disabled">Disabled</option>
                    <option value="snaptrade">SnapTrade</option>
                    <option value="mock">Mock</option>
                  </select>
                </label>
                <label>
                  SnapTrade client ID
                  <input
                    autoComplete="off"
                    spellCheck={false}
                    {...brokerageSyncConfigForm.register("snaptrade_client_id")}
                  />
                </label>
                <label>
                  SnapTrade consumer key
                  <input
                    type="password"
                    autoComplete="new-password"
                    placeholder={
                      brokerageSyncConfigQuery.data?.consumer_key_configured
                        ? "Stored locally. Leave blank to keep the current key."
                        : "Paste your consumer key"
                    }
                    {...brokerageSyncConfigForm.register("snaptrade_consumer_key")}
                  />
                </label>
                <label>
                  Redirect URI
                  <input
                    autoComplete="off"
                    spellCheck={false}
                    {...brokerageSyncConfigForm.register("snaptrade_redirect_uri")}
                  />
                </label>
                <p className="config-help form-grid__full">
                  Saved only to your local <code>.env</code>. The consumer key is write-only in the UI and stays
                  masked after save.
                  {brokerageSyncConfigQuery.data?.consumer_key_masked
                    ? ` Current key: ${brokerageSyncConfigQuery.data.consumer_key_masked}.`
                    : ""}
                </p>
                <div className="form-actions form-grid__full">
                  <button
                    className="button button--primary"
                    type="submit"
                    disabled={saveBrokerageConfigMutation.isPending}
                  >
                    {saveBrokerageConfigMutation.isPending ? "Saving..." : "Save brokerage settings"}
                  </button>
                  <button
                    className="button button--ghost"
                    type="button"
                    onClick={() => {
                      setIsBrokerageConfigOpen(false);
                      brokerageSyncConfigForm.reset({
                        provider: brokerageSyncConfigQuery.data?.provider ?? defaultBrokerageSyncConfig.provider,
                        snaptrade_client_id: brokerageSyncConfigQuery.data?.snaptrade_client_id ?? "",
                        snaptrade_consumer_key: "",
                        snaptrade_redirect_uri:
                          brokerageSyncConfigQuery.data?.snaptrade_redirect_uri ??
                          defaultBrokerageSyncConfig.snaptrade_redirect_uri,
                      });
                    }}
                  >
                    Cancel
                  </button>
                </div>
                {saveBrokerageConfigMutation.isError ? (
                  <p className="status-line status-line--error form-grid__full">
                    {saveBrokerageConfigMutation.error.message}
                  </p>
                ) : null}
              </form>
            ) : null}
          </div>
          {brokerageSyncQuery.isLoading ? <p className="empty-state">Loading brokerage sync status...</p> : null}
          {brokerageSyncQuery.isError ? (
            <p className="status-line status-line--error">{brokerageSyncQuery.error.message}</p>
          ) : null}
          {brokerageSyncQuery.data ? (
            <div className="stack">
              <div className="insight-grid">
                <article className="insight-card">
                  <p>Provider</p>
                  <strong>{brokerageSyncQuery.data.provider_label}</strong>
                  <span>{brokerageSyncQuery.data.enabled ? "Enabled" : "Disabled"}</span>
                </article>
                <article className="insight-card">
                  <p>Linked user</p>
                  <strong>{brokerageSyncQuery.data.user?.external_user_id ?? "Not connected yet"}</strong>
                  <span>
                    {brokerageSyncQuery.data.user?.last_synced_at
                      ? `Last sync ${formatDate(brokerageSyncQuery.data.user.last_synced_at)}`
                      : "Open the connection portal, then run sync"}
                  </span>
                </article>
                <article className="insight-card">
                  <p>Imported records</p>
                  <strong>{brokerageSyncQuery.data.total_synced_holdings} holdings</strong>
                  <span>{brokerageSyncQuery.data.total_synced_transactions} cash events synced</span>
                </article>
              </div>
              {brokerageSyncQuery.data.setup_instructions ? (
                <p className="status-line">{brokerageSyncQuery.data.setup_instructions}</p>
              ) : null}
              {brokerageSyncNotice ? <p className="status-line">{brokerageSyncNotice}</p> : null}
              {lastPortalUrl ? (
                <p className="status-line">
                  Connection portal ready. If it did not open automatically, use{" "}
                  <a href={lastPortalUrl} target="_blank" rel="noreferrer">
                    this portal link
                  </a>
                  .
                </p>
              ) : null}
              {connectMutation.isError ? (
                <p className="status-line status-line--error">{connectMutation.error.message}</p>
              ) : null}
              {syncMutation.isSuccess ? (
                <p className="status-line">
                  Synced {syncMutation.data.accounts_synced} accounts, {syncMutation.data.holdings_synced} holdings,
                  and {syncMutation.data.cash_transactions_synced} cash events.
                </p>
              ) : null}
              {syncMutation.isError ? (
                <p className="status-line status-line--error">{syncMutation.error.message}</p>
              ) : null}
              {syncMutation.data?.warnings.length ? (
                <ul className="warning-list">
                  {syncMutation.data.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : null}
              {brokerageSyncQuery.data.synced_accounts.length ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Account</th>
                      <th>Brokerage</th>
                      <th>Category</th>
                      <th>Holdings</th>
                      <th>Cash events</th>
                      <th>Last synced</th>
                    </tr>
                  </thead>
                  <tbody>
                    {brokerageSyncQuery.data.synced_accounts.map((account) => (
                      <tr key={account.account_id}>
                        <td>
                          <strong>{account.account_name}</strong>
                          <div>{account.account_type}</div>
                        </td>
                        <td>{account.brokerage}</td>
                        <td>{account.category}</td>
                        <td>{account.holdings_count}</td>
                        <td>{account.cash_transactions_count}</td>
                        <td>{account.last_synced_at ? formatDate(account.last_synced_at) : "Not yet"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="empty-state">
                  No synced accounts yet. Connect a provider, finish authorization, then run sync.
                </p>
              )}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="split-layout">
        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Observability</p>
              <h2>Runtime health and request profile</h2>
            </div>
          </div>
          {observabilityQuery.isLoading ? <p className="empty-state">Loading runtime status...</p> : null}
          {observabilityQuery.isError ? (
            <p className="status-line status-line--error">{observabilityQuery.error.message}</p>
          ) : null}
          {observabilityQuery.data ? (
            <div className="stack">
              <div className="insight-grid">
                <article className="insight-card">
                  <p>Environment</p>
                  <strong>{observabilityQuery.data.environment}</strong>
                  <span>Auth {observabilityQuery.data.auth_enabled ? "enabled" : "disabled"}</span>
                </article>
                <article className="insight-card">
                  <p>Database</p>
                  <strong>{observabilityQuery.data.database_ok ? "Healthy" : "Check needed"}</strong>
                  <span>Scheduler {observabilityQuery.data.scheduler_running ? "running" : "stopped"}</span>
                </article>
                <article className="insight-card">
                  <p>Requests</p>
                  <strong>{observabilityQuery.data.total_requests}</strong>
                  <span>Error rate {observabilityQuery.data.error_rate_pct}%</span>
                </article>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Path</th>
                    <th>Count</th>
                    <th>Errors</th>
                    <th>Avg ms</th>
                    <th>Max ms</th>
                  </tr>
                </thead>
                <tbody>
                  {observabilityQuery.data.endpoints.map((endpoint) => (
                    <tr key={endpoint.path}>
                      <td>{endpoint.path}</td>
                      <td>{endpoint.count}</td>
                      <td>{endpoint.error_count}</td>
                      <td>{endpoint.avg_duration_ms}</td>
                      <td>{endpoint.max_duration_ms}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </article>

        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Backup workflow</p>
              <h2>Portable SQLite backup and restore</h2>
            </div>
          </div>
          <div className="stack">
            <p className="status-line">
              Use `./scripts/backup-db.sh` to create a consistent snapshot and `./scripts/restore-db.sh` to restore it.
            </p>
            <div className="insight-grid">
              <article className="insight-card">
                <p>Backup command</p>
                <strong><code>./scripts/backup-db.sh</code></strong>
                <span>Writes a SQLite copy plus JSON manifest in <code>backend/backups/</code></span>
              </article>
              <article className="insight-card">
                <p>Restore command</p>
                <strong><code>./scripts/restore-db.sh /path/to/backup.db</code></strong>
                <span>Stop the app first, then restore into the configured DB path</span>
              </article>
            </div>
          </div>
        </article>
      </section>

      <section className="split-layout">
        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Spreadsheet import</p>
              <h2>Preview CSV or Excel holdings before commit</h2>
            </div>
          </div>
          <div className="form-grid">
            <label className="form-grid__full">
              Upload spreadsheet
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <div className="form-actions">
              <button className="button button--primary" onClick={previewFile} disabled={!selectedFile}>
                Preview import
              </button>
            </div>
          </div>

          {previewMutation.isError ? <p className="status-line status-line--error">{previewMutation.error.message}</p> : null}
          {previewMutation.data ? (
            <div className="stack">
              <p className="status-line">
                Adapter: <strong>{previewMutation.data.adapter_name}</strong> · Rows: {previewMutation.data.row_count}
              </p>
              <div className="insight-grid">
                <article className="insight-card">
                  <p>Brokerages detected</p>
                  <strong>
                    {previewMutation.data.reconciliation.detected_brokerages.length
                      ? previewMutation.data.reconciliation.detected_brokerages.join(", ")
                      : "Not tagged"}
                  </strong>
                  <span>{previewMutation.data.reconciliation.rows_with_account_match} rows matched an account</span>
                </article>
                <article className="insight-card">
                  <p>Suggested account</p>
                  <strong>
                    {previewMutation.data.reconciliation.suggested_account_name
                      ? `${previewMutation.data.reconciliation.suggested_account_name} · ${previewMutation.data.reconciliation.suggested_brokerage}`
                      : "Review before commit"}
                  </strong>
                  <span>{previewMutation.data.reconciliation.account_suggestions.length} possible account target(s)</span>
                </article>
                <article className="insight-card">
                  <p>Needs review</p>
                  <strong>{previewMutation.data.reconciliation.rows_needing_review}</strong>
                  <span>{previewMutation.data.reconciliation.duplicate_rows_in_file} duplicate row(s) in file</span>
                </article>
                <article className="insight-card">
                  <p>Existing lot matches</p>
                  <strong>{previewMutation.data.reconciliation.rows_matching_existing_holdings}</strong>
                  <span>Rows that already match holdings in the suggested account</span>
                </article>
              </div>
              {previewMutation.data.reconciliation.account_suggestions.length ? (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Suggested account</th>
                        <th>Brokerage</th>
                        <th>Matched rows</th>
                        <th>Existing ticker matches</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewMutation.data.reconciliation.account_suggestions.map((suggestion) => (
                        <tr key={suggestion.account_id}>
                          <td>
                            <strong>{suggestion.account_name}</strong>
                            <div>{suggestion.reason}</div>
                          </td>
                          <td>{suggestion.brokerage}</td>
                          <td>{suggestion.matched_rows}</td>
                          <td>{suggestion.matched_existing_holdings}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              {previewMutation.data.warnings.length ? (
                <ul className="warning-list">
                  {previewMutation.data.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : null}
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Source account</th>
                      <th>Brokerage</th>
                      <th>Ticker</th>
                      <th>Shares</th>
                      <th>Cost basis</th>
                      <th>Currency</th>
                      <th>Reconciliation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previewMutation.data.preview_rows.map((row) => (
                      <tr key={row.row_index}>
                        <td>{row.row_index}</td>
                        <td>{row.account_name ?? "—"}</td>
                        <td>{row.brokerage ?? "—"}</td>
                        <td>{row.ticker}</td>
                        <td>{formatNumber(row.shares)}</td>
                        <td>{row.cost_basis}</td>
                        <td>{row.currency}</td>
                        <td>
                          <span className={`import-status import-status--${row.reconciliation_status}`}>
                            {row.reconciliation_status === "review"
                              ? "Review"
                              : row.reconciliation_status === "matched"
                                ? "Matched"
                                : "New"}
                          </span>
                          <div className="import-status__detail">
                            {row.matched_account_name
                              ? `${row.matched_account_name} · ${row.matched_account_brokerage}`
                              : "No account match yet"}
                          </div>
                          {row.review_notes.length ? (
                            <div className="import-status__detail">{row.review_notes.join(" ")}</div>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </article>

        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Commit target</p>
              <h2>Choose where the imported lots land</h2>
            </div>
          </div>
          <form className="form-grid">
            <label>
              Mode
              <select {...accountForm.register("mode")}>
                <option value="existing">Existing account</option>
                <option value="new">Create account on commit</option>
              </select>
            </label>
            {accountForm.watch("mode") === "existing" ? (
              <label>
                Account
                <select {...accountForm.register("account_id")}>
                  <option value="">Select an account</option>
                  {accountsQuery.data?.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name} · {account.brokerage}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <>
                <label>
                  Name
                  <input {...accountForm.register("name")} />
                </label>
                <label>
                  Account type
                  <input {...accountForm.register("account_type")} />
                </label>
                <label>
                  Category
                  <select {...accountForm.register("category")}>
                    <option value="brokerage">Brokerage</option>
                    <option value="retirement">Retirement</option>
                    <option value="india">India</option>
                  </select>
                </label>
                <label>
                  Brokerage
                  <input {...accountForm.register("brokerage")} list="import-brokerage-options" />
                </label>
                <datalist id="import-brokerage-options">
                  {knownBrokerages.map((brokerage) => (
                    <option key={brokerage} value={brokerage} />
                  ))}
                </datalist>
              </>
            )}
            <label className="form-grid__full checkbox-row">
              <input type="checkbox" {...accountForm.register("replace_existing")} />
              Replace all existing holdings in the selected account with this import
            </label>
            <label className="form-grid__full checkbox-row">
              <input
                type="checkbox"
                {...accountForm.register("skip_existing_matching_holdings")}
                disabled={accountForm.watch("replace_existing")}
              />
              Skip exact duplicate lots already present in the target account
            </label>
            <div className="form-actions">
              <button
                className="button button--primary"
                type="button"
                onClick={commitImport}
                disabled={!previewMutation.data || commitMutation.isPending}
              >
                Commit import
              </button>
            </div>
            {commitMutation.isSuccess ? (
              <p className="status-line">
                Imported {commitMutation.data.imported_holdings} holding(s)
                {commitMutation.data.skipped_duplicate_holdings
                  ? ` and skipped ${commitMutation.data.skipped_duplicate_holdings} duplicate lot(s).`
                  : "."}
              </p>
            ) : null}
            {commitMutation.isError ? <p className="status-line status-line--error">{commitMutation.error.message}</p> : null}
          </form>
        </article>
      </section>
    </div>
  );
}
