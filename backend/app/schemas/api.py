from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AccountCreate(APIModel):
    name: str
    account_type: str
    category: str
    brokerage: str


class AccountUpdate(APIModel):
    name: str | None = None
    account_type: str | None = None
    category: str | None = None
    brokerage: str | None = None


class AccountRead(APIModel):
    id: int
    name: str
    account_type: str
    category: str
    brokerage: str
    sync_provider: str | None = None
    sync_status: str | None = None
    last_synced_at: datetime | None = None
    last_sync_error: str | None = None
    created_at: datetime


class HoldingCreate(APIModel):
    account_id: int
    ticker: str
    name: str | None = None
    shares: Decimal
    cost_basis: Decimal
    purchase_date: date
    security_type: str = "equity"
    market: str = "us"
    currency: str = "USD"
    notes: str | None = None


class HoldingUpdate(APIModel):
    account_id: int | None = None
    ticker: str | None = None
    name: str | None = None
    shares: Decimal | None = None
    cost_basis: Decimal | None = None
    purchase_date: date | None = None
    security_type: str | None = None
    market: str | None = None
    currency: str | None = None
    notes: str | None = None


class HoldingRead(APIModel):
    id: int
    account_id: int
    account_name: str
    account_category: str
    brokerage: str
    ticker: str
    name: str | None
    shares: Decimal
    cost_basis: Decimal
    cost_basis_per_share: Decimal
    purchase_date: date
    security_type: str
    market: str
    currency: str
    current_price: Decimal
    current_value: Decimal
    gain_loss: Decimal
    return_pct: Decimal
    notes: str | None


class TransactionCreate(APIModel):
    account_id: int
    ticker: str
    transaction_type: str
    shares: Decimal = Decimal("0")
    price_per_share: Decimal = Decimal("0")
    total_amount: Decimal | None = None
    transaction_date: date
    notes: str | None = None


class TransactionUpdate(APIModel):
    account_id: int | None = None
    ticker: str | None = None
    transaction_type: str | None = None
    shares: Decimal | None = None
    price_per_share: Decimal | None = None
    total_amount: Decimal | None = None
    transaction_date: date | None = None
    notes: str | None = None


class TransactionRead(APIModel):
    id: int
    account_id: int
    account_name: str
    account_category: str
    ticker: str
    transaction_type: str
    shares: Decimal
    price_per_share: Decimal
    total_amount: Decimal
    transaction_date: date
    notes: str | None = None


class PortfolioSummary(APIModel):
    total_value: Decimal = Decimal("0")
    total_cost_basis: Decimal = Decimal("0")
    gain_loss: Decimal = Decimal("0")
    return_pct: Decimal = Decimal("0")
    estimated_dividends: Decimal = Decimal("0")


class AllocationSlice(APIModel):
    ticker: str
    label: str
    value: Decimal
    allocation_pct: Decimal
    gain_loss: Decimal
    return_pct: Decimal


class ExposureSlice(APIModel):
    label: str
    value: Decimal
    exposure_pct: Decimal


class DividendInsight(APIModel):
    ticker: str
    label: str
    annual_income: Decimal
    dividend_yield: Decimal
    contribution_pct: Decimal


class AccountBreakdown(APIModel):
    account_id: int
    account_name: str
    category: str
    value: Decimal
    cost_basis: Decimal
    gain_loss: Decimal
    return_pct: Decimal


class PortfolioResponse(APIModel):
    summary: PortfolioSummary
    category_summaries: dict[str, PortfolioSummary]
    allocation: list[AllocationSlice]
    top_holdings: list[AllocationSlice]
    account_breakdown: list[AccountBreakdown]
    holdings: list[HoldingRead]
    last_updated: date | None = None


class PerformancePoint(APIModel):
    date: date
    portfolio_value: Decimal
    dollar_change: Decimal
    percent_change: Decimal
    benchmarks: dict[str, Decimal | None] = Field(default_factory=dict)


class PerformanceResponse(APIModel):
    category: str
    period: str
    points: list[PerformancePoint]


class CategorySeries(APIModel):
    category: str
    points: list[PerformancePoint]


class CategoryPerformanceResponse(APIModel):
    period: str
    series: list[CategorySeries]


class JobRequest(APIModel):
    tickers: list[str] = Field(default_factory=list)
    include_benchmarks: bool = True


class BackgroundJobRead(APIModel):
    id: str
    job_type: str
    status: str
    payload: dict
    result: dict | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class NormalizedImportRow(APIModel):
    row_index: int
    ticker: str
    name: str | None = None
    shares: Decimal
    cost_basis: Decimal
    purchase_date: date
    security_type: str
    market: str
    currency: str
    account_name: str | None = None
    brokerage: str | None = None
    cost_basis_source: str = "reported"
    ticker_inferred: bool = False
    reconciliation_status: str = "new"
    matched_account_id: int | None = None
    matched_account_name: str | None = None
    matched_account_brokerage: str | None = None
    matched_existing_holdings: int = 0
    duplicate_row_count: int = 1
    review_notes: list[str] = Field(default_factory=list)


class ImportAccountSuggestion(APIModel):
    account_id: int
    account_name: str
    brokerage: str
    matched_rows: int
    matched_existing_holdings: int
    reason: str


class ImportReconciliationSummary(APIModel):
    suggested_account_id: int | None = None
    suggested_account_name: str | None = None
    suggested_brokerage: str | None = None
    duplicate_rows_in_file: int = 0
    rows_matching_existing_holdings: int = 0
    rows_with_account_match: int = 0
    rows_needing_review: int = 0
    detected_brokerages: list[str] = Field(default_factory=list)
    account_suggestions: list[ImportAccountSuggestion] = Field(default_factory=list)


class ImportPreviewResponse(APIModel):
    job_id: int
    adapter_name: str
    status: str
    row_count: int
    warnings: list[str]
    reconciliation: ImportReconciliationSummary
    preview_rows: list[NormalizedImportRow]


class ImportCommitAccount(APIModel):
    name: str
    account_type: str
    category: str
    brokerage: str


class ImportCommitRequest(APIModel):
    account_id: int | None = None
    account: ImportCommitAccount | None = None
    replace_existing: bool = False
    skip_existing_matching_holdings: bool = True


class ImportCommitResponse(APIModel):
    job_id: int
    status: str
    imported_holdings: int
    skipped_duplicate_holdings: int = 0
    created_account_id: int | None = None


class ImportJobRead(APIModel):
    id: int
    filename: str
    adapter_name: str
    status: str
    warnings: list[str]
    created_at: datetime
    committed_at: datetime | None
    reconciliation: ImportReconciliationSummary
    preview_rows: list[NormalizedImportRow]


class SnapshotRead(APIModel):
    snapshot_date: date
    category: str
    total_value: Decimal
    total_cost_basis: Decimal


class QuantStatsMetrics(APIModel):
    period: str
    trading_days: int
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    cagr_pct: Decimal
    volatility_pct: Decimal
    max_drawdown_pct: Decimal
    win_rate_pct: Decimal
    avg_return_pct: Decimal
    avg_win_pct: Decimal
    avg_loss_pct: Decimal
    best_day_pct: Decimal
    worst_day_pct: Decimal
    value_at_risk_pct: Decimal
    conditional_value_at_risk_pct: Decimal
    ulcer_index: Decimal
    payoff_ratio: Decimal
    profit_factor: Decimal


class AnalyticsResponse(APIModel):
    sector_allocation: list[AllocationSlice]
    top_gainers: list[AllocationSlice]
    top_losers: list[AllocationSlice]
    diversification_score: Decimal
    time_weighted_return_ytd: Decimal
    time_weighted_return_1y: Decimal
    max_drawdown_1y: Decimal
    top_three_concentration_pct: Decimal
    annual_dividend_income: Decimal
    portfolio_yield_pct: Decimal
    benchmark_spread_1y: list["BenchmarkSpread"]
    index_exposure: list[ExposureSlice]
    top_dividend_positions: list[DividendInsight]
    quantstats: QuantStatsMetrics | None = None


class InvestmentMonthSummary(APIModel):
    month: str
    contributions: Decimal
    withdrawals: Decimal
    dividends: Decimal
    net_investment: Decimal
    cumulative_net_investment: Decimal


class CashFlowBreakdown(APIModel):
    label: str
    amount: Decimal
    count: int


class InvestmentMonthInsight(APIModel):
    month: str
    amount: Decimal


class InvestmentSummaryResponse(APIModel):
    year: int
    category: str
    transaction_count: int
    contributions: Decimal
    withdrawals: Decimal
    dividends: Decimal
    net_investment: Decimal
    average_monthly_net: Decimal
    average_monthly_dividends: Decimal
    active_months: int
    best_month: InvestmentMonthInsight | None = None
    largest_outflow_month: InvestmentMonthInsight | None = None
    monthly: list[InvestmentMonthSummary]
    type_breakdown: list[CashFlowBreakdown]


class BenchmarkSpread(APIModel):
    label: str
    portfolio_return: Decimal
    benchmark_return: Decimal
    spread_pct: Decimal


class AuthLoginRequest(APIModel):
    password: str


class AuthSessionRead(APIModel):
    enabled: bool
    authenticated: bool
    expires_at: datetime | None = None


class AuthLoginResponse(AuthSessionRead):
    token: str | None = None


class EndpointMetric(APIModel):
    path: str
    count: int
    error_count: int
    avg_duration_ms: Decimal
    max_duration_ms: Decimal


class ObservabilityResponse(APIModel):
    environment: str
    database_backend: str
    auth_enabled: bool
    scheduler_running: bool
    database_ok: bool
    last_price_refresh: date | None = None
    uptime_seconds: int
    total_requests: int
    total_errors: int
    error_rate_pct: Decimal
    endpoints: list[EndpointMetric]


class BrokerageSyncUserRead(APIModel):
    provider: str
    local_profile_id: str
    external_user_id: str
    status: str
    last_synced_at: datetime | None = None
    last_error: str | None = None
    last_portal_expires_at: datetime | None = None
    created_at: datetime


class BrokerageSyncedAccountRead(APIModel):
    account_id: int
    account_name: str
    brokerage: str
    account_type: str
    category: str
    sync_status: str | None = None
    last_synced_at: datetime | None = None
    last_sync_error: str | None = None
    holdings_count: int
    cash_transactions_count: int


class BrokerageSyncStatusResponse(APIModel):
    provider: str
    provider_label: str
    enabled: bool
    configured: bool
    setup_instructions: str | None = None
    user: BrokerageSyncUserRead | None = None
    synced_accounts: list[BrokerageSyncedAccountRead]
    total_synced_holdings: int = 0
    total_synced_transactions: int = 0


class BrokerageSyncConnectResponse(APIModel):
    provider: str
    provider_label: str
    portal_url: str
    expires_at: datetime | None = None
    user_created: bool
    user: BrokerageSyncUserRead


class BrokerageSyncRunResponse(APIModel):
    provider: str
    provider_label: str
    status: str
    synced_at: datetime
    accounts_synced: int
    holdings_synced: int
    cash_transactions_synced: int
    warnings: list[str] = Field(default_factory=list)


class BrokerageSyncConfigRead(APIModel):
    provider: str
    snaptrade_client_id: str | None = None
    snaptrade_redirect_uri: str | None = None
    consumer_key_configured: bool
    consumer_key_masked: str | None = None


class BrokerageSyncConfigUpdate(APIModel):
    provider: str
    snaptrade_client_id: str | None = None
    snaptrade_consumer_key: str | None = None
    snaptrade_redirect_uri: str | None = None
    clear_consumer_key: bool = False
