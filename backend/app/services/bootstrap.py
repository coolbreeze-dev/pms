from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Benchmark


DEFAULT_BENCHMARKS = [
    ("S&P 500", "SPY"),
    ("NASDAQ", "QQQ"),
    ("FTSE 100", "ISF.L"),
    ("BSE 500", "BSE500"),
]


def seed_reference_data(session: Session) -> None:
    existing = {ticker for ticker in session.scalars(select(Benchmark.ticker))}
    for name, ticker in DEFAULT_BENCHMARKS:
        if ticker not in existing:
            session.add(Benchmark(name=name, ticker=ticker))
    session.commit()

