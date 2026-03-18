from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, select

from app.db.session import SessionLocal, init_db
from app.models import Account, Benchmark, FxRate, Holding, PortfolioSnapshot, PriceHistory, Transaction
from app.services.bootstrap import seed_reference_data
from app.services.jobs import _upsert_fx_rate, _upsert_price, _write_snapshots, router


DEMO_ACCOUNTS = [
    {
        "name": "Vanguard Taxable",
        "account_type": "Individual Brokerage",
        "category": "brokerage",
        "brokerage": "Vanguard",
        "holdings": [
            ("VTI", "Vanguard Total Stock Market ETF", "18.5", "4700", "2024-01-05", "etf", "us", "USD"),
            ("AAPL", "Apple", "12", "2100", "2024-02-14", "equity", "us", "USD"),
            ("MSFT", "Microsoft", "7", "2650", "2024-04-18", "equity", "us", "USD"),
        ],
        "transactions": [
            ("VTI", "buy", "8", "245", "1960", "2026-01-12", "New year allocation"),
            ("AAPL", "buy", "2", "198", "396", "2026-02-19", "Added on pullback"),
            ("CASH", "deposit", "0", "0", "1500", "2026-03-01", "Monthly contribution"),
        ],
    },
    {
        "name": "Fidelity Roth IRA",
        "account_type": "Roth IRA",
        "category": "retirement",
        "brokerage": "Fidelity",
        "holdings": [
            ("QQQ", "Invesco QQQ", "9", "3950", "2023-12-20", "etf", "us", "USD"),
            ("NVDA", "NVIDIA", "6", "2900", "2024-03-22", "equity", "us", "USD"),
        ],
        "transactions": [
            ("QQQ", "buy", "3", "431", "1293", "2026-01-08", "Retirement rebalance"),
            ("CASH", "deposit", "0", "0", "700", "2026-02-01", "IRA contribution"),
            ("NVDA", "dividend", "0", "0", "42", "2026-02-28", "Cash dividend"),
        ],
    },
    {
        "name": "ICICI Direct India",
        "account_type": "Personal (India)",
        "category": "india",
        "brokerage": "ICICIDirect",
        "holdings": [
            ("INFY", "Infosys", "55", "93000", "2024-02-01", "equity", "india", "INR"),
            ("HDFCBANK", "HDFC Bank", "20", "34000", "2024-05-10", "equity", "india", "INR"),
        ],
        "transactions": [
            ("INFY", "buy", "10", "1670", "16700", "2026-01-17", "SIP top-up"),
            ("HDFCBANK", "buy", "4", "1725", "6900", "2026-02-10", "Monthly purchase"),
            ("CASH", "withdrawal", "0", "0", "3000", "2026-03-04", "Moved cash to savings"),
        ],
    },
]


def reset_demo_data() -> None:
    init_db()
    with SessionLocal() as session:
        seed_reference_data(session)
        for model in [PortfolioSnapshot, PriceHistory, FxRate, Transaction, Holding, Account]:
            session.execute(delete(model))
        session.commit()

        unique_targets: dict[str, tuple[str, Decimal]] = {}
        currencies_to_seed: set[str] = set()

        for account_payload in DEMO_ACCOUNTS:
            account = Account(
                name=account_payload["name"],
                account_type=account_payload["account_type"],
                category=account_payload["category"],
                brokerage=account_payload["brokerage"],
            )
            session.add(account)
            session.flush()

            for (
                ticker,
                name,
                shares,
                cost_basis,
                purchase_date,
                security_type,
                market,
                currency,
            ) in account_payload["holdings"]:
                shares_decimal = Decimal(shares)
                cost_basis_decimal = Decimal(cost_basis)
                session.add(
                    Holding(
                        account_id=account.id,
                        ticker=ticker,
                        name=name,
                        shares=shares_decimal,
                        cost_basis=cost_basis_decimal,
                        cost_basis_per_share=(cost_basis_decimal / shares_decimal).quantize(
                            Decimal("0.00000001")
                        ),
                        purchase_date=date.fromisoformat(purchase_date),
                        security_type=security_type,
                        market=market,
                        currency=currency,
                        notes="Seeded demo data",
                    )
                )
                unique_targets[ticker] = (currency, (cost_basis_decimal / shares_decimal))
                if currency != "USD":
                    currencies_to_seed.add(currency)

            for (
                ticker,
                transaction_type,
                shares,
                price_per_share,
                total_amount,
                transaction_date,
                notes,
            ) in account_payload.get("transactions", []):
                session.add(
                    Transaction(
                        account_id=account.id,
                        ticker=ticker,
                        transaction_type=transaction_type,
                        shares=Decimal(shares),
                        price_per_share=Decimal(price_per_share),
                        total_amount=Decimal(total_amount),
                        transaction_date=date.fromisoformat(transaction_date),
                        notes=notes,
                    )
                )

        benchmark_rows = session.scalars(select(Benchmark)).all()
        history_start = date.today() - timedelta(days=365)
        seen_price_keys: set[tuple[str, date]] = set()

        for ticker, (currency, reference_price) in unique_targets.items():
            history = router.history(
                ticker,
                history_start,
                date.today(),
                currency=currency,
                reference_price=reference_price,
            )
            quote = router.quote(ticker, currency=currency, reference_price=reference_price)
            for point_date, close_price in history.points:
                key = (ticker, point_date)
                if key in seen_price_keys:
                    continue
                seen_price_keys.add(key)
                _upsert_price(
                    session,
                    ticker,
                    point_date,
                    close_price,
                    history.currency,
                    history.source,
                    dividend_yield=quote.dividend_yield if point_date == quote.as_of else None,
                )
        for currency in sorted(currencies_to_seed):
            fx_rate = router.fx_rate(currency, "USD")
            _upsert_fx_rate(session, currency, "USD", date.today(), fx_rate, "router")

        for benchmark in benchmark_rows:
            history = router.history(benchmark.ticker, history_start, date.today(), currency="USD")
            for point_date, close_price in history.points:
                key = (benchmark.ticker, point_date)
                if key in seen_price_keys:
                    continue
                seen_price_keys.add(key)
                _upsert_price(session, benchmark.ticker, point_date, close_price, "USD", history.source)

        _write_snapshots(session)
        session.commit()


if __name__ == "__main__":
    reset_demo_data()
    print("Demo data seeded.")
