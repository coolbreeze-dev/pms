from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import math
import os
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from app.models import Account, Benchmark, FxRate, Holding, PortfolioSnapshot, PriceHistory, Transaction
from app.schemas.api import (
    AccountBreakdown,
    AllocationSlice,
    AnalyticsResponse,
    BenchmarkSpread,
    CategoryPerformanceResponse,
    CategorySeries,
    DividendInsight,
    ExposureSlice,
    HoldingRead,
    PerformancePoint,
    PerformanceResponse,
    PortfolioResponse,
    PortfolioSummary,
    QuantStatsMetrics,
    SnapshotRead,
)


DECIMAL_ZERO = Decimal("0")
PERIOD_WINDOWS = {
    "1d": 1,
    "1w": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
    "ytd": None,
    "all": None,
}

SECTOR_MAP = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "GOOGL": "Communication",
    "AMZN": "Consumer",
    "TSLA": "Consumer",
    "QQQ": "Index ETF",
    "SPY": "Index ETF",
    "VTI": "Index ETF",
}

INDEX_PROXY_MAP = {
    "AAPL": "NASDAQ 100",
    "AMZN": "S&P 500",
    "GOOGL": "NASDAQ 100",
    "HDFCBANK": "BSE 500",
    "INFY": "BSE 500",
    "MSFT": "NASDAQ 100",
    "NVDA": "NASDAQ 100",
    "QQQ": "NASDAQ 100",
    "SPY": "S&P 500",
    "TSLA": "NASDAQ 100",
    "VTI": "US Total Market",
}

EXTERNAL_FLOW_TYPES = {"deposit": Decimal("1"), "withdrawal": Decimal("-1")}
QUANTSTATS_PERIOD = "1y"


@dataclass
class EvaluatedHolding:
    holding: Holding
    current_price: Decimal
    current_value: Decimal
    cost_basis_usd: Decimal
    gain_loss: Decimal
    return_pct: Decimal
    dividend_yield: Decimal


def _decimal(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value))


def _metric_decimal(value: object, places: str = "0.01", scale: str = "1") -> Decimal:
    if value is None:
        return DECIMAL_ZERO
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return DECIMAL_ZERO
    if math.isnan(numeric_value) or math.isinf(numeric_value):
        return DECIMAL_ZERO
    return (Decimal(str(numeric_value)) * Decimal(scale)).quantize(Decimal(places))


def _latest_price_map(session: Session, tickers: set[str]) -> dict[str, PriceHistory]:
    if not tickers:
        return {}
    subquery = (
        select(PriceHistory.ticker, func.max(PriceHistory.price_date).label("max_date"))
        .where(PriceHistory.ticker.in_(tickers))
        .group_by(PriceHistory.ticker)
        .subquery()
    )
    rows = session.execute(
        select(PriceHistory).join(
            subquery,
            and_(
                PriceHistory.ticker == subquery.c.ticker,
                PriceHistory.price_date == subquery.c.max_date,
            ),
        )
    ).scalars()
    return {row.ticker: row for row in rows}


def _latest_fx_map(session: Session, currencies: set[str]) -> dict[str, Decimal]:
    latest: dict[str, Decimal] = {"USD": Decimal("1")}
    currencies = {currency.upper() for currency in currencies if currency.upper() != "USD"}
    if not currencies:
        return latest
    subquery = (
        select(FxRate.from_currency, func.max(FxRate.rate_date).label("max_date"))
        .where(FxRate.from_currency.in_(currencies), FxRate.to_currency == "USD")
        .group_by(FxRate.from_currency)
        .subquery()
    )
    rows = session.execute(
        select(FxRate).join(
            subquery,
            and_(
                FxRate.from_currency == subquery.c.from_currency,
                FxRate.rate_date == subquery.c.max_date,
            ),
        )
    ).scalars()
    for row in rows:
        latest[row.from_currency] = _decimal(row.rate)
    return latest


def _base_holdings_query(category: str | None = None, account_id: int | None = None) -> Select:
    query = select(Holding, Account).join(Account, Holding.account_id == Account.id)
    if category and category != "all":
        query = query.where(Account.category == category)
    if account_id is not None:
        query = query.where(Account.id == account_id)
    return query.order_by(Account.name, Holding.ticker, Holding.purchase_date)


def evaluate_holdings(
    session: Session, category: str | None = None, account_id: int | None = None, search: str | None = None
) -> list[EvaluatedHolding]:
    rows = session.execute(_base_holdings_query(category, account_id)).all()
    holdings_with_accounts = [(holding, account) for holding, account in rows]
    if search:
        search_lower = search.lower()
        holdings_with_accounts = [
            (holding, account)
            for holding, account in holdings_with_accounts
            if search_lower in holding.ticker.lower() or search_lower in account.name.lower()
        ]
    tickers = {holding.ticker for holding, _ in holdings_with_accounts}
    latest_prices = _latest_price_map(session, tickers)
    latest_fx = _latest_fx_map(session, {holding.currency for holding, _ in holdings_with_accounts})
    evaluated: list[EvaluatedHolding] = []
    for holding, _account in holdings_with_accounts:
        price_row = latest_prices.get(holding.ticker)
        native_price = _decimal(price_row.close_price) if price_row else _decimal(holding.cost_basis_per_share)
        fx_rate = latest_fx.get(holding.currency.upper(), Decimal("1"))
        current_value = (native_price * _decimal(holding.shares) * fx_rate).quantize(Decimal("0.0001"))
        cost_basis = (_decimal(holding.cost_basis) * fx_rate).quantize(Decimal("0.0001"))
        gain_loss = (current_value - cost_basis).quantize(Decimal("0.0001"))
        return_pct = (
            ((gain_loss / cost_basis) * Decimal("100")).quantize(Decimal("0.01"))
            if cost_basis
            else DECIMAL_ZERO
        )
        evaluated.append(
            EvaluatedHolding(
                holding=holding,
                current_price=(native_price * fx_rate).quantize(Decimal("0.0001")),
                current_value=current_value,
                cost_basis_usd=cost_basis,
                gain_loss=gain_loss,
                return_pct=return_pct,
                dividend_yield=_decimal(price_row.dividend_yield) if price_row and price_row.dividend_yield else DECIMAL_ZERO,
            )
        )
    return evaluated


def serialize_holding(session: Session, evaluated: EvaluatedHolding) -> HoldingRead:
    account = session.get(Account, evaluated.holding.account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found for holding.")
    return HoldingRead(
        id=evaluated.holding.id,
        account_id=account.id,
        account_name=account.name,
        account_category=account.category,
        brokerage=account.brokerage,
        ticker=evaluated.holding.ticker,
        name=evaluated.holding.name,
        shares=evaluated.holding.shares,
        cost_basis=evaluated.holding.cost_basis,
        cost_basis_per_share=evaluated.holding.cost_basis_per_share,
        purchase_date=evaluated.holding.purchase_date,
        security_type=evaluated.holding.security_type,
        market=evaluated.holding.market,
        currency=evaluated.holding.currency,
        current_price=evaluated.current_price,
        current_value=evaluated.current_value,
        gain_loss=evaluated.gain_loss,
        return_pct=evaluated.return_pct,
        notes=evaluated.holding.notes,
    )


def _summary_from_holdings(evaluated: list[EvaluatedHolding]) -> PortfolioSummary:
    total_value = sum((item.current_value for item in evaluated), start=DECIMAL_ZERO)
    total_cost_basis = sum((item.cost_basis_usd for item in evaluated), start=DECIMAL_ZERO)
    gain_loss = total_value - total_cost_basis
    dividends = sum(
        (item.current_value * item.dividend_yield for item in evaluated),
        start=DECIMAL_ZERO,
    ).quantize(Decimal("0.0001"))
    return PortfolioSummary(
        total_value=total_value.quantize(Decimal("0.0001")),
        total_cost_basis=total_cost_basis.quantize(Decimal("0.0001")),
        gain_loss=gain_loss.quantize(Decimal("0.0001")),
        return_pct=(
            ((gain_loss / total_cost_basis) * Decimal("100")).quantize(Decimal("0.01"))
            if total_cost_basis
            else DECIMAL_ZERO
        ),
        estimated_dividends=dividends,
    )


def _allocation_from_holdings(evaluated: list[EvaluatedHolding]) -> list[AllocationSlice]:
    total_value = sum((item.current_value for item in evaluated), start=DECIMAL_ZERO)
    grouped: dict[str, dict[str, Decimal | str]] = {}
    for item in evaluated:
        entry = grouped.setdefault(
            item.holding.ticker,
            {
                "label": item.holding.name or item.holding.ticker,
                "value": DECIMAL_ZERO,
                "cost_basis": DECIMAL_ZERO,
            },
        )
        entry["value"] = _decimal(entry["value"]) + item.current_value
        entry["cost_basis"] = _decimal(entry["cost_basis"]) + item.cost_basis_usd
    slices: list[AllocationSlice] = []
    for ticker, aggregate in grouped.items():
        value = _decimal(aggregate["value"])
        cost_basis = _decimal(aggregate["cost_basis"])
        gain_loss = value - cost_basis
        allocation_pct = ((value / total_value) * Decimal("100")).quantize(Decimal("0.01")) if total_value else DECIMAL_ZERO
        return_pct = ((gain_loss / cost_basis) * Decimal("100")).quantize(Decimal("0.01")) if cost_basis else DECIMAL_ZERO
        slices.append(
            AllocationSlice(
                ticker=ticker,
                label=str(aggregate["label"]),
                value=value.quantize(Decimal("0.0001")),
                allocation_pct=allocation_pct,
                gain_loss=gain_loss.quantize(Decimal("0.0001")),
                return_pct=return_pct,
            )
        )
    return sorted(slices, key=lambda item: item.value, reverse=True)


def _account_breakdown(session: Session, evaluated: list[EvaluatedHolding]) -> list[AccountBreakdown]:
    grouped: dict[int, dict[str, Decimal | str]] = {}
    for item in evaluated:
        account = session.get(Account, item.holding.account_id)
        if account is None:
            continue
        entry = grouped.setdefault(
            account.id,
            {
                "account_name": account.name,
                "category": account.category,
                "value": DECIMAL_ZERO,
                "cost_basis": DECIMAL_ZERO,
            },
        )
        entry["value"] = _decimal(entry["value"]) + item.current_value
        entry["cost_basis"] = _decimal(entry["cost_basis"]) + item.cost_basis_usd
    result: list[AccountBreakdown] = []
    for account_id, aggregate in grouped.items():
        value = _decimal(aggregate["value"])
        cost_basis = _decimal(aggregate["cost_basis"])
        gain_loss = value - cost_basis
        return_pct = ((gain_loss / cost_basis) * Decimal("100")).quantize(Decimal("0.01")) if cost_basis else DECIMAL_ZERO
        result.append(
            AccountBreakdown(
                account_id=account_id,
                account_name=str(aggregate["account_name"]),
                category=str(aggregate["category"]),
                value=value.quantize(Decimal("0.0001")),
                cost_basis=cost_basis.quantize(Decimal("0.0001")),
                gain_loss=gain_loss.quantize(Decimal("0.0001")),
                return_pct=return_pct,
            )
        )
    return sorted(result, key=lambda item: item.value, reverse=True)


def get_portfolio(session: Session, category: str = "all") -> PortfolioResponse:
    active = evaluate_holdings(session, category=category)
    all_category_summaries = {
        "all": _summary_from_holdings(evaluate_holdings(session, category="all")),
        "brokerage": _summary_from_holdings(evaluate_holdings(session, category="brokerage")),
        "retirement": _summary_from_holdings(evaluate_holdings(session, category="retirement")),
        "india": _summary_from_holdings(evaluate_holdings(session, category="india")),
    }
    latest_date = session.scalar(select(func.max(PriceHistory.price_date)))
    serialized = [serialize_holding(session, item) for item in active]
    allocation = _allocation_from_holdings(active)
    return PortfolioResponse(
        summary=_summary_from_holdings(active),
        category_summaries=all_category_summaries,
        allocation=allocation,
        top_holdings=allocation[:10],
        account_breakdown=_account_breakdown(session, active),
        holdings=serialized,
        last_updated=latest_date,
    )


def list_holdings(session: Session, category: str | None = None, search: str | None = None) -> list[HoldingRead]:
    return [serialize_holding(session, item) for item in evaluate_holdings(session, category=category, search=search)]


def _period_start(session: Session, period: str, category: str = "all") -> date:
    today = date.today()
    if period == "ytd":
        return date(today.year, 1, 1)
    if period == "all":
        earliest = session.scalar(
            select(func.min(Holding.purchase_date)).join(Account).where(
                Account.category == category if category != "all" else True
            )
        )
        return earliest or (today - timedelta(days=180))
    window = PERIOD_WINDOWS.get(period)
    if window is None:
        raise HTTPException(status_code=400, detail=f"Unsupported period '{period}'.")
    return today - timedelta(days=window)


def _history_map(session: Session, tickers: set[str], start: date) -> dict[str, list[PriceHistory]]:
    if not tickers:
        return {}
    rows = session.scalars(
        select(PriceHistory)
        .where(PriceHistory.ticker.in_(tickers), PriceHistory.price_date >= start)
        .order_by(PriceHistory.ticker, PriceHistory.price_date)
    ).all()
    grouped: dict[str, list[PriceHistory]] = defaultdict(list)
    for row in rows:
        grouped[row.ticker].append(row)
    return grouped


def _forward_fill(points: list[PriceHistory], target_date: date) -> Decimal | None:
    latest = None
    for point in points:
        if point.price_date > target_date:
            break
        latest = point
    return _decimal(latest.close_price) if latest else None


def _external_flow_map(session: Session, category: str, start: date, end: date) -> dict[date, Decimal]:
    query = select(Transaction, Account).join(Account, Transaction.account_id == Account.id).where(
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= end,
        Transaction.transaction_type.in_(tuple(EXTERNAL_FLOW_TYPES.keys())),
    )
    if category != "all":
        query = query.where(Account.category == category)

    flows: dict[date, Decimal] = defaultdict(lambda: DECIMAL_ZERO)
    for transaction, _account in session.execute(query).all():
        direction = EXTERNAL_FLOW_TYPES.get(transaction.transaction_type, DECIMAL_ZERO)
        flows[transaction.transaction_date] += _decimal(transaction.total_amount) * direction
    return dict(flows)


def _time_weighted_return(
    session: Session, category: str, period: str
) -> Decimal:
    performance = get_performance(session, category, period)
    points = performance.points
    if len(points) < 2:
        return DECIMAL_ZERO

    external_flows = _external_flow_map(session, category, points[0].date, points[-1].date)
    growth_factor = Decimal("1")

    for previous, current in zip(points, points[1:]):
        start_value = _decimal(previous.portfolio_value)
        end_value = _decimal(current.portfolio_value)
        if start_value <= 0:
            continue
        net_external_flow = external_flows.get(current.date, DECIMAL_ZERO)
        daily_return = (end_value - start_value - net_external_flow) / start_value
        growth_factor *= Decimal("1") + daily_return

    return ((growth_factor - Decimal("1")) * Decimal("100")).quantize(Decimal("0.01"))


def _daily_return_series(session: Session, category: str, period: str):
    try:
        import pandas as pd
    except Exception:
        return None

    performance = get_performance(session, category, period)
    points = performance.points
    if len(points) < 2:
        return None

    external_flows = _external_flow_map(session, category, points[0].date, points[-1].date)
    returns: dict[object, float] = {}
    for previous, current in zip(points, points[1:]):
        start_value = _decimal(previous.portfolio_value)
        end_value = _decimal(current.portfolio_value)
        if start_value <= 0:
            continue
        net_external_flow = external_flows.get(current.date, DECIMAL_ZERO)
        daily_return = (end_value - start_value - net_external_flow) / start_value
        returns[pd.Timestamp(current.date)] = float(daily_return)

    if len(returns) < 2:
        return None
    return pd.Series(returns, name="portfolio").sort_index()


def _max_drawdown(points: list[PerformancePoint]) -> Decimal:
    peak_value = DECIMAL_ZERO
    worst_drawdown = DECIMAL_ZERO
    for point in points:
        current_value = _decimal(point.portfolio_value)
        peak_value = max(peak_value, current_value)
        if peak_value <= 0:
            continue
        drawdown = ((current_value - peak_value) / peak_value * Decimal("100")).quantize(Decimal("0.01"))
        worst_drawdown = min(worst_drawdown, drawdown)
    return worst_drawdown


def _benchmark_spreads(session: Session, category: str, period: str) -> list[BenchmarkSpread]:
    performance = get_performance(session, category, period)
    if not performance.points:
        return []
    latest_point = performance.points[-1]
    portfolio_return = _decimal(latest_point.percent_change)
    spreads = [
        BenchmarkSpread(
            label=label,
            portfolio_return=portfolio_return,
            benchmark_return=_decimal(benchmark_return),
            spread_pct=(portfolio_return - _decimal(benchmark_return)).quantize(Decimal("0.01")),
        )
        for label, benchmark_return in latest_point.benchmarks.items()
        if benchmark_return is not None
    ]
    return sorted(spreads, key=lambda item: item.spread_pct, reverse=True)


def _quantstats_metrics(session: Session, category: str, period: str = QUANTSTATS_PERIOD) -> QuantStatsMetrics | None:
    try:
        mpl_config_dir = Path("/tmp/mpl")
        mpl_config_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))
        import quantstats as qs
    except Exception:
        return None

    returns = _daily_return_series(session, category, period)
    if returns is None or len(returns) < 2:
        return None

    return QuantStatsMetrics(
        period=period,
        trading_days=len(returns),
        sharpe_ratio=_metric_decimal(qs.stats.sharpe(returns)),
        sortino_ratio=_metric_decimal(qs.stats.sortino(returns)),
        calmar_ratio=_metric_decimal(qs.stats.calmar(returns)),
        cagr_pct=_metric_decimal(qs.stats.cagr(returns), scale="100"),
        volatility_pct=_metric_decimal(qs.stats.volatility(returns), scale="100"),
        max_drawdown_pct=_metric_decimal(qs.stats.max_drawdown(returns), scale="100"),
        win_rate_pct=_metric_decimal(qs.stats.win_rate(returns), scale="100"),
        avg_return_pct=_metric_decimal(qs.stats.avg_return(returns), scale="100"),
        avg_win_pct=_metric_decimal(qs.stats.avg_win(returns), scale="100"),
        avg_loss_pct=_metric_decimal(qs.stats.avg_loss(returns), scale="100"),
        best_day_pct=_metric_decimal(qs.stats.best(returns), scale="100"),
        worst_day_pct=_metric_decimal(qs.stats.worst(returns), scale="100"),
        value_at_risk_pct=_metric_decimal(qs.stats.value_at_risk(returns), scale="100"),
        conditional_value_at_risk_pct=_metric_decimal(qs.stats.cvar(returns), scale="100"),
        ulcer_index=_metric_decimal(qs.stats.ulcer_index(returns)),
        payoff_ratio=_metric_decimal(qs.stats.payoff_ratio(returns)),
        profit_factor=_metric_decimal(qs.stats.profit_factor(returns)),
    )


def _index_exposure(evaluated: list[EvaluatedHolding]) -> list[ExposureSlice]:
    total_value = sum((item.current_value for item in evaluated), start=DECIMAL_ZERO)
    grouped: dict[str, Decimal] = defaultdict(lambda: DECIMAL_ZERO)
    for item in evaluated:
        label = INDEX_PROXY_MAP.get(
            item.holding.ticker,
            "BSE 500" if item.holding.market == "india" else "Direct / Active",
        )
        grouped[label] += item.current_value

    return sorted(
        [
            ExposureSlice(
                label=label,
                value=value.quantize(Decimal("0.0001")),
                exposure_pct=((value / total_value) * Decimal("100")).quantize(Decimal("0.01"))
                if total_value
                else DECIMAL_ZERO,
            )
            for label, value in grouped.items()
        ],
        key=lambda item: item.value,
        reverse=True,
    )


def _dividend_insights(
    evaluated: list[EvaluatedHolding],
) -> tuple[Decimal, Decimal, list[DividendInsight]]:
    total_value = sum((item.current_value for item in evaluated), start=DECIMAL_ZERO)
    grouped_income: dict[str, dict[str, Decimal | str]] = defaultdict(
        lambda: {"label": "", "annual_income": DECIMAL_ZERO, "value": DECIMAL_ZERO}
    )
    for item in evaluated:
        income = (item.current_value * item.dividend_yield).quantize(Decimal("0.0001"))
        if income <= 0:
            continue
        entry = grouped_income[item.holding.ticker]
        entry["label"] = item.holding.name or item.holding.ticker
        entry["annual_income"] = _decimal(entry["annual_income"]) + income
        entry["value"] = _decimal(entry["value"]) + item.current_value

    annual_income = sum(
        (_decimal(entry["annual_income"]) for entry in grouped_income.values()),
        start=DECIMAL_ZERO,
    ).quantize(Decimal("0.0001"))
    portfolio_yield_pct = (
        ((annual_income / total_value) * Decimal("100")).quantize(Decimal("0.01"))
        if total_value
        else DECIMAL_ZERO
    )
    top_positions = sorted(
        [
            DividendInsight(
                ticker=ticker,
                label=str(entry["label"]),
                annual_income=_decimal(entry["annual_income"]).quantize(Decimal("0.0001")),
                dividend_yield=(
                    ((_decimal(entry["annual_income"]) / _decimal(entry["value"])) * Decimal("100")).quantize(
                        Decimal("0.01")
                    )
                    if _decimal(entry["value"])
                    else DECIMAL_ZERO
                ),
                contribution_pct=(
                    ((_decimal(entry["annual_income"]) / annual_income) * Decimal("100")).quantize(
                        Decimal("0.01")
                    )
                    if annual_income
                    else DECIMAL_ZERO
                ),
            )
            for ticker, entry in grouped_income.items()
        ],
        key=lambda item: item.annual_income,
        reverse=True,
    )
    return annual_income, portfolio_yield_pct, top_positions[:5]


def get_performance(session: Session, category: str, period: str) -> PerformanceResponse:
    evaluated = evaluate_holdings(session, category=category)
    start = _period_start(session, period, category=category)
    end = date.today()
    tickers = {item.holding.ticker for item in evaluated}
    history_map = _history_map(session, tickers, start)
    benchmark_rows = session.scalars(select(Benchmark)).all()
    benchmark_map = _history_map(session, {row.ticker for row in benchmark_rows}, start)
    dates = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    points: list[PerformancePoint] = []
    baseline: Decimal | None = None
    benchmark_baselines: dict[str, Decimal] = {}
    for current_date in dates:
        total_value = DECIMAL_ZERO
        for item in evaluated:
            if current_date < item.holding.purchase_date:
                continue
            price = _forward_fill(history_map.get(item.holding.ticker, []), current_date)
            if price is None:
                price = _decimal(item.holding.cost_basis_per_share)
            fx_rate = Decimal("1")
            if item.holding.currency.upper() != "USD":
                fx_rate = _latest_fx_map(session, {item.holding.currency}).get(item.holding.currency.upper(), Decimal("1"))
            total_value += price * _decimal(item.holding.shares) * fx_rate
        if baseline is None:
            baseline = total_value or Decimal("1")
        benchmark_values: dict[str, Decimal | None] = {}
        for benchmark in benchmark_rows:
            series = benchmark_map.get(benchmark.ticker, [])
            benchmark_price = _forward_fill(series, current_date)
            if benchmark_price is None:
                benchmark_values[benchmark.name] = None
                continue
            starting_price = benchmark_baselines.get(benchmark.ticker)
            if starting_price is None:
                benchmark_baselines[benchmark.ticker] = benchmark_price or Decimal("1")
                starting_price = benchmark_baselines[benchmark.ticker]
            benchmark_values[benchmark.name] = (
                ((benchmark_price - starting_price) / starting_price) * Decimal("100")
            ).quantize(Decimal("0.01"))
        dollar_change = total_value - baseline
        percent_change = ((dollar_change / baseline) * Decimal("100")).quantize(Decimal("0.01")) if baseline else DECIMAL_ZERO
        points.append(
            PerformancePoint(
                date=current_date,
                portfolio_value=total_value.quantize(Decimal("0.0001")),
                dollar_change=dollar_change.quantize(Decimal("0.0001")),
                percent_change=percent_change,
                benchmarks=benchmark_values,
            )
        )
    return PerformanceResponse(category=category, period=period, points=points)


def get_category_performance(session: Session, period: str) -> CategoryPerformanceResponse:
    series = [
        CategorySeries(category=category, points=get_performance(session, category, period).points)
        for category in ["brokerage", "retirement", "india"]
    ]
    return CategoryPerformanceResponse(period=period, series=series)


def list_snapshots(session: Session) -> list[SnapshotRead]:
    rows = session.scalars(
        select(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_date.desc(), PortfolioSnapshot.category)
    ).all()
    return [
        SnapshotRead(
            snapshot_date=row.snapshot_date,
            category=row.category,
            total_value=row.total_value,
            total_cost_basis=row.total_cost_basis,
        )
        for row in rows
    ]


def get_last_updated(session: Session) -> date | None:
    return session.scalar(select(func.max(PriceHistory.price_date)))


def get_analytics(session: Session, category: str = "all") -> AnalyticsResponse:
    evaluated = evaluate_holdings(session, category=category)
    allocation = _allocation_from_holdings(evaluated)
    total_value = sum((item.current_value for item in evaluated), start=DECIMAL_ZERO) or Decimal("1")
    hhi = sum(((item.value / total_value) ** 2 for item in allocation), start=DECIMAL_ZERO)
    diversification_score = ((Decimal("1") - hhi) * Decimal("100")).quantize(Decimal("0.01"))
    performance_1y = get_performance(session, category, "1y")
    sector_buckets: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"value": DECIMAL_ZERO, "cost_basis": DECIMAL_ZERO})
    for item in evaluated:
        sector = SECTOR_MAP.get(item.holding.ticker, "Other")
        sector_buckets[sector]["value"] += item.current_value
        sector_buckets[sector]["cost_basis"] += item.cost_basis_usd
    sector_allocation = []
    for sector, aggregate in sector_buckets.items():
        value = aggregate["value"]
        gain_loss = value - aggregate["cost_basis"]
        sector_allocation.append(
            AllocationSlice(
                ticker=sector,
                label=sector,
                value=value.quantize(Decimal("0.0001")),
                allocation_pct=((value / total_value) * Decimal("100")).quantize(Decimal("0.01")),
                gain_loss=gain_loss.quantize(Decimal("0.0001")),
                return_pct=((gain_loss / aggregate["cost_basis"]) * Decimal("100")).quantize(Decimal("0.01")) if aggregate["cost_basis"] else DECIMAL_ZERO,
            )
        )
    sorted_by_return = sorted(allocation, key=lambda item: item.return_pct, reverse=True)
    annual_dividend_income, portfolio_yield_pct, top_dividend_positions = _dividend_insights(evaluated)
    return AnalyticsResponse(
        sector_allocation=sorted(sector_allocation, key=lambda item: item.value, reverse=True),
        top_gainers=sorted_by_return[:5],
        top_losers=list(reversed(sorted_by_return[-5:])),
        diversification_score=diversification_score,
        time_weighted_return_ytd=_time_weighted_return(session, category, "ytd"),
        time_weighted_return_1y=_time_weighted_return(session, category, "1y"),
        max_drawdown_1y=_max_drawdown(performance_1y.points),
        top_three_concentration_pct=sum(
            (item.allocation_pct for item in allocation[:3]),
            start=DECIMAL_ZERO,
        ).quantize(Decimal("0.01")),
        annual_dividend_income=annual_dividend_income,
        portfolio_yield_pct=portfolio_yield_pct,
        benchmark_spread_1y=_benchmark_spreads(session, category, "1y"),
        index_exposure=_index_exposure(evaluated),
        top_dividend_positions=top_dividend_positions,
        quantstats=_quantstats_metrics(session, category, QUANTSTATS_PERIOD),
    )
