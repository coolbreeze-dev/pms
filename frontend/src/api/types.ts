export type AccountCategory = "all" | "brokerage" | "retirement" | "india";
export type Period = "1d" | "1w" | "1m" | "3m" | "6m" | "1y" | "ytd" | "all";

export interface Account {
  id: number;
  name: string;
  account_type: string;
  category: Exclude<AccountCategory, "all">;
  brokerage: string;
  sync_provider?: string | null;
  sync_status?: string | null;
  last_synced_at?: string | null;
  last_sync_error?: string | null;
  created_at: string;
}

export interface Holding {
  id: number;
  account_id: number;
  account_name: string;
  account_category: Exclude<AccountCategory, "all">;
  brokerage: string;
  ticker: string;
  name?: string | null;
  shares: string;
  cost_basis: string;
  cost_basis_per_share: string;
  purchase_date: string;
  security_type: string;
  market: string;
  currency: string;
  current_price: string;
  current_value: string;
  gain_loss: string;
  return_pct: string;
  notes?: string | null;
}

export interface Transaction {
  id: number;
  account_id: number;
  account_name: string;
  account_category: Exclude<AccountCategory, "all">;
  ticker: string;
  transaction_type: string;
  shares: string;
  price_per_share: string;
  total_amount: string;
  transaction_date: string;
  notes?: string | null;
}

export interface PortfolioSummary {
  total_value: string;
  total_cost_basis: string;
  gain_loss: string;
  return_pct: string;
  estimated_dividends: string;
}

export interface AllocationSlice {
  ticker: string;
  label: string;
  value: string;
  allocation_pct: string;
  gain_loss: string;
  return_pct: string;
}

export interface ExposureSlice {
  label: string;
  value: string;
  exposure_pct: string;
}

export interface DividendInsight {
  ticker: string;
  label: string;
  annual_income: string;
  dividend_yield: string;
  contribution_pct: string;
}

export interface AccountBreakdown {
  account_id: number;
  account_name: string;
  category: string;
  value: string;
  cost_basis: string;
  gain_loss: string;
  return_pct: string;
}

export interface PortfolioResponse {
  summary: PortfolioSummary;
  category_summaries: Record<string, PortfolioSummary>;
  allocation: AllocationSlice[];
  top_holdings: AllocationSlice[];
  account_breakdown: AccountBreakdown[];
  holdings: Holding[];
  last_updated?: string | null;
}

export interface PerformancePoint {
  date: string;
  portfolio_value: string;
  dollar_change: string;
  percent_change: string;
  benchmarks: Record<string, string | null>;
}

export interface PerformanceResponse {
  category: AccountCategory;
  period: Period;
  points: PerformancePoint[];
}

export interface CategorySeries {
  category: AccountCategory;
  points: PerformancePoint[];
}

export interface CategoryPerformanceResponse {
  period: Period;
  series: CategorySeries[];
}

export interface BenchmarkSpread {
  label: string;
  portfolio_return: string;
  benchmark_return: string;
  spread_pct: string;
}

export interface QuantStatsMetrics {
  period: string;
  trading_days: number;
  sharpe_ratio: string;
  sortino_ratio: string;
  calmar_ratio: string;
  cagr_pct: string;
  volatility_pct: string;
  max_drawdown_pct: string;
  win_rate_pct: string;
  avg_return_pct: string;
  avg_win_pct: string;
  avg_loss_pct: string;
  best_day_pct: string;
  worst_day_pct: string;
  value_at_risk_pct: string;
  conditional_value_at_risk_pct: string;
  ulcer_index: string;
  payoff_ratio: string;
  profit_factor: string;
}

export interface AnalyticsResponse {
  sector_allocation: AllocationSlice[];
  top_gainers: AllocationSlice[];
  top_losers: AllocationSlice[];
  diversification_score: string;
  time_weighted_return_ytd: string;
  time_weighted_return_1y: string;
  max_drawdown_1y: string;
  top_three_concentration_pct: string;
  annual_dividend_income: string;
  portfolio_yield_pct: string;
  benchmark_spread_1y: BenchmarkSpread[];
  index_exposure: ExposureSlice[];
  top_dividend_positions: DividendInsight[];
  quantstats?: QuantStatsMetrics | null;
}

export interface InvestmentMonthSummary {
  month: string;
  contributions: string;
  withdrawals: string;
  dividends: string;
  net_investment: string;
  cumulative_net_investment: string;
}

export interface CashFlowBreakdown {
  label: string;
  amount: string;
  count: number;
}

export interface InvestmentMonthInsight {
  month: string;
  amount: string;
}

export interface InvestmentSummaryResponse {
  year: number;
  category: AccountCategory;
  transaction_count: number;
  contributions: string;
  withdrawals: string;
  dividends: string;
  net_investment: string;
  average_monthly_net: string;
  average_monthly_dividends: string;
  active_months: number;
  best_month?: InvestmentMonthInsight | null;
  largest_outflow_month?: InvestmentMonthInsight | null;
  monthly: InvestmentMonthSummary[];
  type_breakdown: CashFlowBreakdown[];
}

export interface NormalizedImportRow {
  row_index: number;
  ticker: string;
  name?: string | null;
  shares: string;
  cost_basis: string;
  purchase_date: string;
  security_type: string;
  market: string;
  currency: string;
  account_name?: string | null;
  brokerage?: string | null;
  cost_basis_source: string;
  ticker_inferred: boolean;
  reconciliation_status: string;
  matched_account_id?: number | null;
  matched_account_name?: string | null;
  matched_account_brokerage?: string | null;
  matched_existing_holdings: number;
  duplicate_row_count: number;
  review_notes: string[];
}

export interface ImportAccountSuggestion {
  account_id: number;
  account_name: string;
  brokerage: string;
  matched_rows: number;
  matched_existing_holdings: number;
  reason: string;
}

export interface ImportReconciliationSummary {
  suggested_account_id?: number | null;
  suggested_account_name?: string | null;
  suggested_brokerage?: string | null;
  duplicate_rows_in_file: number;
  rows_matching_existing_holdings: number;
  rows_with_account_match: number;
  rows_needing_review: number;
  detected_brokerages: string[];
  account_suggestions: ImportAccountSuggestion[];
}

export interface ImportPreviewResponse {
  job_id: number;
  adapter_name: string;
  status: string;
  row_count: number;
  warnings: string[];
  reconciliation: ImportReconciliationSummary;
  preview_rows: NormalizedImportRow[];
}

export interface ImportCommitResponse {
  job_id: number;
  status: string;
  imported_holdings: number;
  skipped_duplicate_holdings: number;
  created_account_id?: number | null;
}

export interface BackgroundJob {
  id: string;
  job_type: string;
  status: string;
  payload: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface AuthSession {
  enabled: boolean;
  authenticated: boolean;
  expires_at?: string | null;
}

export interface AuthLoginResponse extends AuthSession {
  token?: string | null;
}

export interface EndpointMetric {
  path: string;
  count: number;
  error_count: number;
  avg_duration_ms: string;
  max_duration_ms: string;
}

export interface ObservabilityResponse {
  environment: string;
  database_backend: string;
  auth_enabled: boolean;
  scheduler_running: boolean;
  database_ok: boolean;
  last_price_refresh?: string | null;
  uptime_seconds: number;
  total_requests: number;
  total_errors: number;
  error_rate_pct: string;
  endpoints: EndpointMetric[];
}

export interface BrokerageSyncUser {
  provider: string;
  local_profile_id: string;
  external_user_id: string;
  status: string;
  last_synced_at?: string | null;
  last_error?: string | null;
  last_portal_expires_at?: string | null;
  created_at: string;
}

export interface BrokerageSyncedAccount {
  account_id: number;
  account_name: string;
  brokerage: string;
  account_type: string;
  category: Exclude<AccountCategory, "all">;
  sync_status?: string | null;
  last_synced_at?: string | null;
  last_sync_error?: string | null;
  holdings_count: number;
  cash_transactions_count: number;
}

export interface BrokerageSyncStatusResponse {
  provider: string;
  provider_label: string;
  enabled: boolean;
  configured: boolean;
  setup_instructions?: string | null;
  user?: BrokerageSyncUser | null;
  synced_accounts: BrokerageSyncedAccount[];
  total_synced_holdings: number;
  total_synced_transactions: number;
}

export interface BrokerageSyncConnectResponse {
  provider: string;
  provider_label: string;
  portal_url: string;
  expires_at?: string | null;
  user_created: boolean;
  user: BrokerageSyncUser;
}

export interface BrokerageSyncRunResponse {
  provider: string;
  provider_label: string;
  status: string;
  synced_at: string;
  accounts_synced: number;
  holdings_synced: number;
  cash_transactions_synced: number;
  warnings: string[];
}

export interface BrokerageSyncConfig {
  provider: string;
  snaptrade_client_id?: string | null;
  snaptrade_redirect_uri?: string | null;
  consumer_key_configured: boolean;
  consumer_key_masked?: string | null;
}
