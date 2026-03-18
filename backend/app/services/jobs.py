from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import BackgroundJob, Benchmark, FxRate, Holding, PortfolioSnapshot, PriceHistory
from app.providers.market_data import MarketDataRouter
from app.schemas.api import JobRequest
from app.services.portfolio import get_portfolio


scheduler = BackgroundScheduler(daemon=True)
router = MarketDataRouter()


def ensure_scheduler_started() -> None:
    if not scheduler.running:
        scheduler.start()


def _upsert_price(session: Session, ticker: str, price_date: date, price: Decimal, currency: str, source: str, dividend_yield: Decimal | None = None) -> None:
    existing = session.scalar(
        select(PriceHistory).where(
            and_(PriceHistory.ticker == ticker, PriceHistory.price_date == price_date)
        )
    )
    if existing:
        existing.close_price = price
        existing.currency = currency
        existing.source = source
        if dividend_yield is not None:
            existing.dividend_yield = dividend_yield
    else:
        session.add(
            PriceHistory(
                ticker=ticker,
                price_date=price_date,
                close_price=price,
                currency=currency,
                source=source,
                dividend_yield=dividend_yield,
            )
        )


def _upsert_fx_rate(session: Session, from_currency: str, to_currency: str, rate_date: date, rate: Decimal, source: str) -> None:
    existing = session.scalar(
        select(FxRate).where(
            and_(
                FxRate.from_currency == from_currency,
                FxRate.to_currency == to_currency,
                FxRate.rate_date == rate_date,
            )
        )
    )
    if existing:
        existing.rate = rate
        existing.source = source
    else:
        session.add(
            FxRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate_date=rate_date,
                rate=rate,
                source=source,
            )
        )


def _write_snapshots(session: Session) -> None:
    for category in ["all", "brokerage", "retirement", "india"]:
        portfolio = get_portfolio(session, category=category)
        existing = session.scalar(
            select(PortfolioSnapshot).where(
                and_(
                    PortfolioSnapshot.snapshot_date == date.today(),
                    PortfolioSnapshot.category == category,
                )
            )
        )
        if existing:
            existing.total_value = portfolio.summary.total_value
            existing.total_cost_basis = portfolio.summary.total_cost_basis
        else:
            session.add(
                PortfolioSnapshot(
                    snapshot_date=date.today(),
                    category=category,
                    total_value=portfolio.summary.total_value,
                    total_cost_basis=portfolio.summary.total_cost_basis,
                )
            )


def run_refresh_job(session_factory, job_id: str) -> None:
    session: Session = session_factory()
    try:
        job = session.get(BackgroundJob, job_id)
        if not job:
            return
        job.status = "running"
        session.commit()

        payload = job.payload or {}
        requested_tickers = set(payload.get("tickers", []))
        include_benchmarks = payload.get("include_benchmarks", True)
        holdings = session.scalars(select(Holding)).all()
        benchmarks = session.scalars(select(Benchmark)).all() if include_benchmarks else []

        ticker_targets = requested_tickers or {holding.ticker for holding in holdings}
        refreshed_rows = 0
        date_start = date.today() - timedelta(days=365)

        unique_holdings: dict[str, Holding] = {}
        for holding in holdings:
            if holding.ticker in ticker_targets and holding.ticker not in unique_holdings:
                unique_holdings[holding.ticker] = holding

        for holding in unique_holdings.values():
            history = router.history(
                holding.ticker,
                date_start,
                date.today(),
                currency=holding.currency,
                reference_price=holding.cost_basis_per_share,
            )
            quote = router.quote(
                holding.ticker, currency=holding.currency, reference_price=holding.cost_basis_per_share
            )
            for point_date, close_price in history.points:
                _upsert_price(
                    session,
                    holding.ticker,
                    point_date,
                    close_price,
                    history.currency,
                    history.source,
                    dividend_yield=quote.dividend_yield if point_date == quote.as_of else None,
                )
                refreshed_rows += 1
            if holding.currency.upper() != "USD":
                fx_rate = router.fx_rate(holding.currency.upper(), "USD")
                _upsert_fx_rate(
                    session,
                    holding.currency.upper(),
                    "USD",
                    date.today(),
                    fx_rate,
                    source="router",
                )

        for benchmark in benchmarks:
            history = router.history(benchmark.ticker, date_start, date.today(), currency="USD")
            for point_date, close_price in history.points:
                _upsert_price(
                    session,
                    benchmark.ticker,
                    point_date,
                    close_price,
                    history.currency,
                    history.source,
                )
                refreshed_rows += 1

        _write_snapshots(session)
        job.status = "completed"
        job.result = {
            "refreshed_rows": refreshed_rows,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        job.completed_at = datetime.now(timezone.utc)
        session.commit()
    except Exception as exc:
        session.rollback()
        job = session.get(BackgroundJob, job_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            session.commit()
    finally:
        session.close()


def enqueue_refresh_job(session: Session, session_factory, request: JobRequest) -> BackgroundJob:
    ensure_scheduler_started()
    job = BackgroundJob(
        id=str(uuid4()),
        job_type="refresh_prices",
        status="pending",
        payload=request.model_dump(),
    )
    session.add(job)
    session.commit()
    scheduler.add_job(
        run_refresh_job,
        trigger=DateTrigger(run_date=datetime.now(timezone.utc)),
        id=job.id,
        replace_existing=True,
        args=[session_factory, job.id],
    )
    session.refresh(job)
    return job
