from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Transaction
from app.schemas.api import (
    CashFlowBreakdown,
    InvestmentMonthInsight,
    InvestmentMonthSummary,
    InvestmentSummaryResponse,
    TransactionCreate,
    TransactionRead,
    TransactionUpdate,
)


DECIMAL_ZERO = Decimal("0")
CONTRIBUTION_TYPES = {"buy", "deposit"}
WITHDRAWAL_TYPES = {"sell", "withdrawal"}
DIVIDEND_TYPES = {"dividend"}


def _year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def _transaction_query(category: str | None = None, year: int | None = None):
    query = select(Transaction, Account).join(Account, Transaction.account_id == Account.id)
    if category and category != "all":
        query = query.where(Account.category == category)
    if year is not None:
        start_date, end_date = _year_bounds(year)
        query = query.where(Transaction.transaction_date >= start_date, Transaction.transaction_date <= end_date)
    return query.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())


def _serialize_transaction(transaction: Transaction, account: Account) -> TransactionRead:
    return TransactionRead(
        id=transaction.id,
        account_id=account.id,
        account_name=account.name,
        account_category=account.category,
        ticker=transaction.ticker,
        transaction_type=transaction.transaction_type,
        shares=transaction.shares,
        price_per_share=transaction.price_per_share,
        total_amount=transaction.total_amount,
        transaction_date=transaction.transaction_date,
        notes=transaction.notes,
    )


def _computed_total_amount(shares: Decimal, price_per_share: Decimal, total_amount: Decimal | None) -> Decimal:
    if total_amount is not None and not (
        total_amount == DECIMAL_ZERO and shares > DECIMAL_ZERO and price_per_share > DECIMAL_ZERO
    ):
        return total_amount
    return (shares * price_per_share).quantize(Decimal("0.0001"))


def list_transactions(session: Session, category: str | None = None, year: int | None = None) -> list[TransactionRead]:
    rows = session.execute(_transaction_query(category=category, year=year)).all()
    return [_serialize_transaction(transaction, account) for transaction, account in rows]


def create_transaction(session: Session, payload: TransactionCreate) -> TransactionRead:
    account = session.get(Account, payload.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")

    transaction = Transaction(
        account_id=payload.account_id,
        ticker=payload.ticker.upper(),
        transaction_type=payload.transaction_type,
        shares=payload.shares,
        price_per_share=payload.price_per_share,
        total_amount=_computed_total_amount(payload.shares, payload.price_per_share, payload.total_amount),
        transaction_date=payload.transaction_date,
        notes=payload.notes,
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return _serialize_transaction(transaction, account)


def update_transaction(session: Session, transaction_id: int, payload: TransactionUpdate) -> TransactionRead:
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    data = payload.model_dump(exclude_none=True)
    for field, value in data.items():
        if field == "ticker":
            value = value.upper()
        setattr(transaction, field, value)

    if "total_amount" in data:
        transaction.total_amount = _computed_total_amount(
            transaction.shares, transaction.price_per_share, data["total_amount"]
        )
    elif "shares" in data or "price_per_share" in data:
        transaction.total_amount = _computed_total_amount(
            transaction.shares, transaction.price_per_share, None
        )

    session.commit()
    session.refresh(transaction)
    account = session.get(Account, transaction.account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found for transaction.")
    return _serialize_transaction(transaction, account)


def delete_transaction(session: Session, transaction_id: int) -> None:
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    session.delete(transaction)
    session.commit()


def get_investment_summary(
    session: Session, category: str = "all", year: int | None = None
) -> InvestmentSummaryResponse:
    active_year = year or date.today().year
    rows = session.execute(_transaction_query(category=category, year=active_year)).all()

    contributions = DECIMAL_ZERO
    withdrawals = DECIMAL_ZERO
    dividends = DECIMAL_ZERO
    monthly_rollup: dict[int, dict[str, Decimal]] = {
        month: {
            "contributions": DECIMAL_ZERO,
            "withdrawals": DECIMAL_ZERO,
            "dividends": DECIMAL_ZERO,
            "net_investment": DECIMAL_ZERO,
        }
        for month in range(1, 13)
    }
    type_breakdown: dict[str, dict[str, Decimal | int]] = {}

    for transaction, _account in rows:
        amount = Decimal(str(transaction.total_amount))
        month_bucket = monthly_rollup[transaction.transaction_date.month]
        type_entry = type_breakdown.setdefault(
            transaction.transaction_type,
            {"amount": DECIMAL_ZERO, "count": 0},
        )
        type_entry["amount"] = Decimal(str(type_entry["amount"])) + amount
        type_entry["count"] = int(type_entry["count"]) + 1
        if transaction.transaction_type in CONTRIBUTION_TYPES:
            contributions += amount
            month_bucket["contributions"] += amount
            month_bucket["net_investment"] += amount
        elif transaction.transaction_type in WITHDRAWAL_TYPES:
            withdrawals += amount
            month_bucket["withdrawals"] += amount
            month_bucket["net_investment"] -= amount
        elif transaction.transaction_type in DIVIDEND_TYPES:
            dividends += amount
            month_bucket["dividends"] += amount

    cumulative_net = DECIMAL_ZERO
    monthly = [
        InvestmentMonthSummary(
            month=date(active_year, month, 1).strftime("%b"),
            contributions=values["contributions"].quantize(Decimal("0.0001")),
            withdrawals=values["withdrawals"].quantize(Decimal("0.0001")),
            dividends=values["dividends"].quantize(Decimal("0.0001")),
            net_investment=values["net_investment"].quantize(Decimal("0.0001")),
            cumulative_net_investment=(cumulative_net := (cumulative_net + values["net_investment"])).quantize(
                Decimal("0.0001")
            ),
        )
        for month, values in monthly_rollup.items()
    ]

    active_months = sum(1 for row in monthly if row.contributions or row.withdrawals or row.dividends)
    best_month = max(monthly, key=lambda row: row.net_investment, default=None)
    largest_outflow_month = min(monthly, key=lambda row: row.net_investment, default=None)

    type_rollup = [
        CashFlowBreakdown(
            label=transaction_type.replace("_", " ").title(),
            amount=Decimal(str(values["amount"])).quantize(Decimal("0.0001")),
            count=int(values["count"]),
        )
        for transaction_type, values in sorted(
            type_breakdown.items(), key=lambda item: Decimal(str(item[1]["amount"])), reverse=True
        )
    ]

    net_investment = (contributions - withdrawals).quantize(Decimal("0.0001"))

    return InvestmentSummaryResponse(
        year=active_year,
        category=category,
        transaction_count=len(rows),
        contributions=contributions.quantize(Decimal("0.0001")),
        withdrawals=withdrawals.quantize(Decimal("0.0001")),
        dividends=dividends.quantize(Decimal("0.0001")),
        net_investment=net_investment,
        average_monthly_net=(net_investment / Decimal("12")).quantize(Decimal("0.0001")),
        average_monthly_dividends=(dividends / Decimal("12")).quantize(Decimal("0.0001")),
        active_months=active_months,
        best_month=(
            InvestmentMonthInsight(month=best_month.month, amount=best_month.net_investment)
            if best_month and best_month.net_investment > DECIMAL_ZERO
            else None
        ),
        largest_outflow_month=(
            InvestmentMonthInsight(month=largest_outflow_month.month, amount=largest_outflow_month.net_investment)
            if largest_outflow_month and largest_outflow_month.net_investment < DECIMAL_ZERO
            else None
        ),
        monthly=monthly,
        type_breakdown=type_rollup,
    )
