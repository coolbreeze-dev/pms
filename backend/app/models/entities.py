from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    brokerage: Mapped[str] = mapped_column(String(64), nullable=False)
    sync_provider: Mapped[Optional[str]] = mapped_column(String(32))
    sync_external_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    sync_authorization_id: Mapped[Optional[str]] = mapped_column(String(128))
    sync_status: Mapped[Optional[str]] = mapped_column(String(32))
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_sync_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    holdings: Mapped[list["Holding"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    ticker: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    shares: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cost_basis_per_share: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    security_type: Mapped[str] = mapped_column(String(32), nullable=False, default="equity")
    market: Mapped[str] = mapped_column(String(32), nullable=False, default="us")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    import_source: Mapped[Optional[str]] = mapped_column(String(128))
    import_job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("import_jobs.id", ondelete="SET NULL"))
    sync_provider: Mapped[Optional[str]] = mapped_column(String(32))
    sync_external_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    account: Mapped["Account"] = relationship(back_populates="holdings")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    ticker: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(16), nullable=False)
    shares: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price_per_share: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    sync_provider: Mapped[Optional[str]] = mapped_column(String(32))
    sync_external_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    account: Mapped["Account"] = relationship(back_populates="transactions")


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (UniqueConstraint("ticker", "price_date", name="uq_price_history_ticker_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="fallback")
    dividend_yield: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", "rate_date", name="uq_fx_pair_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="fallback")


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    ticker: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class EtfGroup(Base):
    __tablename__ = "etf_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    tickers_csv: Mapped[str] = mapped_column(Text, nullable=False)
    benchmark_ticker: Mapped[Optional[str]] = mapped_column(String(64))


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_date", "category", name="uq_snapshot_date_category"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="all")
    total_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    total_cost_basis: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(128))
    adapter_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    committed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    rows: Mapped[list["ImportRow"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="ImportRow.row_index"
    )


class ImportRow(Base):
    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"))
    row_index: Mapped[int] = mapped_column(nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="previewed")
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    job: Mapped["ImportJob"] = relationship(back_populates="rows")


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class BrokerageSyncUser(Base):
    __tablename__ = "brokerage_sync_users"
    __table_args__ = (
        UniqueConstraint("provider", "local_profile_id", name="uq_brokerage_sync_provider_profile"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    local_profile_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_user_secret: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="linked")
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_portal_url: Mapped[Optional[str]] = mapped_column(Text)
    last_portal_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
